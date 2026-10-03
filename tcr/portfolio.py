"""Loan tape validation and representative-firm portfolio from public data (Eurostat, Damodaran, Pillar 3 CQ5)."""
import csv
from pathlib import Path

import duckdb
import numpy as np

SIZE_CLASSES = {"small", "medium", "large", "all"}
AMOUNTS = ("revenue", "ebitda", "financial_debt", "exposure", "ghg_t")


def validate(rows, countries, known_nace):
    """Apply the loan tape rules (spec section 4). Returns (valid rows, rejected rows with the failed rule)."""
    ok, rejected, seen = [], [], set()
    for r in rows:
        rule = None
        if r["loan_id"] in seen:
            rule = "loan_id not unique"
        elif not r.get("firm_id"):
            rule = "firm_id missing"
        elif r["country"] not in countries:
            rule = "country not in scope"
        elif r["nace"] not in known_nace:
            rule = "nace not mapped"
        elif r["size_class"] not in SIZE_CLASSES:
            rule = "size_class invalid"
        elif any(r[k] is None or np.isnan(r[k]) for k in AMOUNTS if k in r):
            rule = "missing amount"
        elif r["revenue"] <= 0:
            rule = "revenue <= 0"
        elif r["ebitda"] <= 0:
            rule = "ebitda <= 0 (Merton asset value undefined)"
        elif r["financial_debt"] < 0 or r["exposure"] < 0:
            rule = "negative debt or exposure"
        seen.add(r["loan_id"])
        (rejected if rule else ok).append({**r, "rule": rule} if rule else r)
    return ok, rejected


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def damodaran(raw):
    """Industry -> (EV/EBITDA of positive-EBITDA firms, std deviation of firm value), Damodaran Europe."""
    with open(Path(raw) / "vebitdaEurope.csv", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0][3] == "EV/EBITDA", rows[0]  # first EV/EBITDA column = "Only positive EBITDA firms"
    mult = {r[0]: float(r[3]) for r in rows[1:] if r[3] != "NA"}
    sig = {r["Industry Name"]: float(r["Std Deviation in Firm Value"]) for r in read_csv(Path(raw) / "optvarEurope.csv")}
    return {k: (mult[k], sig[k]) for k in mult if k in sig}


def representative_tape(raw, ref, countries, v_over_d):
    """One loan per country and A64 industry. Amounts in EUR, 2023. Exposure = CQ5 section loans split by value added."""
    smap = {r["a64"]: r for r in read_csv(Path(ref) / "sector_map.csv")}
    na = {(g, n, i): v for g, n, i, v in duckdb.sql(
        f"select geo, nace_r2, na_item, OBS_VALUE from read_csv_auto('{raw}/eurostat_nama_a64.csv')").fetchall()}
    ghg = {(g, n): v for g, n, v in duckdb.sql(
        f"select geo, nace_r2, OBS_VALUE from read_csv_auto('{raw}/eurostat_air_emissions.csv')").fetchall()}
    mult = {k: v[0] for k, v in damodaran(raw).items()}
    cq5 = {(r["country"], r["section"]): float(r["gross_carrying_eur_m"]) for r in read_csv(Path(ref) / "cq5_weights.csv")}

    def val(c, n, i):
        v = na.get((c, n, i))
        return np.nan if v is None else float(v)

    tape = []
    for c in countries:
        gva_section = {}
        for n, s in smap.items():
            gva_section[s["section"]] = gva_section.get(s["section"], 0.0) + np.nan_to_num(val(c, n, "B1G"))
        for n, s in smap.items():
            p1, b1g = val(c, n, "P1"), val(c, n, "B1G")
            margin = (b1g - val(c, n, "D1") - val(c, n, "D29X39")) / p1
            revenue = p1 * 1e6
            ebitda = margin * revenue
            share = b1g / gva_section[s["section"]] if gva_section[s["section"]] else np.nan
            tape.append({
                "loan_id": f"{c}-{n}", "firm_id": f"{c}-{n}", "country": c, "nace": n, "size_class": "all",
                "revenue": revenue, "ebitda": ebitda,
                "financial_debt": ebitda * mult[s["damodaran_industry"]] / v_over_d,
                "exposure": cq5.get((c, s["section"]), 0.0) * 1e6 * share,
                "ghg_t": float(ghg[(c, n)]) * 1e3 if ghg.get((c, n)) is not None else np.nan,
            })
    return tape, smap


BACH_SIZES = {"1a": "small", "1b": "medium", "2": "large"}


def covers(a64, division):
    """True if the A64 code (e.g. "C10-C12", "C31_C32", "B") contains the NACE division (e.g. "C11")."""
    if a64 == division or (len(a64) == 1 and division[0] == a64):
        return True
    parts = a64.replace("_", "-").split("-")
    return (len(parts) == 2 and division[0] == a64[0] and division[1:].isdigit()
            and int(parts[0][1:]) <= int(division[1:]) <= int(parts[1][1:]))


def quantile_draw(q1, q2, q3, u):
    """Piecewise-linear quantile function through BACH Q1, median, Q3, extended linearly beyond them."""
    return np.where(u < 0.5, q2 + (u - 0.5) * (q2 - q1) / 0.25, q2 + (u - 0.5) * (q3 - q2) / 0.25)


def quantile_position(q1, q2, q3, v):
    """Inverse of quantile_draw: the probability level at which the quantile function equals v, clipped to [0, 1)."""
    if v <= q2:
        u = 0.5 + (v - q2) * 0.25 / (q2 - q1) if q2 > q1 else 0.0
    else:
        u = 0.5 + (v - q2) * 0.25 / (q3 - q2) if q3 > q2 else 1.0
    return min(max(u, 0.0), 0.999)


def bach_tape(raw, ref, countries, year, firms_per_cell, seed, margin_floor, v_over_d, leverage_cap):
    """Firm-level tape from BACH quartiles (division x size class, variable sample).

    margin = R32 (gross operating profit / net turnover), drawn above the margin floor (EBITDA > 0 rule);
    leverage = net debt / gross operating profit, the inverse of R27, whose quartiles map one to one when R27 Q1 > 0.
    Exposure = CQ5 section loans split across cells by amounts owed to credit institutions (L2).
    Sections without BACH cells keep the representative firm. Returns (tape, smap, stats).
    """
    raw = Path(raw)
    pq = raw / "bach_it_de.parquet"
    if not pq.exists():
        src = next(raw.glob("2*.csv"))  # file inside bach.zip, named by release date
        duckdb.sql(f"""copy (select country, year, sector, size, sample, nb_firms, total_assets, turnover,
            r32_q1, r32_q2, r32_q3, r27_q1, r27_q2, r27_q3, L2_wm
            from read_csv('{src}', delim=';', header=true, skip=1, all_varchar=true)
            where country in ('IT','DE')) to '{pq}' (format parquet)""")
    rep, smap = representative_tape(raw, ref, countries, v_over_d)
    e0 = {(r["country"], r["nace"]): r["ghg_t"] / r["revenue"] for r in rep}
    cq5 = {(r["country"], r["section"]): float(r["gross_carrying_eur_m"]) for r in read_csv(Path(ref) / "cq5_weights.csv")}
    cells = duckdb.sql(f"""select country, sector, size, cast(nb_firms as double), cast(turnover as double),
        cast(total_assets as double) * cast(L2_wm as double) / 100,
        cast(r32_q1 as double), cast(r32_q2 as double), cast(r32_q3 as double),
        cast(r27_q1 as double), cast(r27_q2 as double), cast(r27_q3 as double)
        from '{pq}' where year = '{year}' and sample = '0' and size in ('1a','1b','2') and length(sector) = 3
        and r32_q1 is not null and r32_q2 is not null and r32_q3 is not null and r27_q1 is not null and cast(r27_q1 as double) > 0
        and r27_q2 is not null and r27_q3 is not null and cast(nb_firms as double) > 0""").fetchall()
    rows = []
    for c, div, size, n, turnover, bank, *q in cells:
        a64 = next((k for k in smap if covers(k, div)), None)
        if c in countries and a64 and bank and bank > 0:
            rows.append((c, div, size, n, turnover, bank, a64, smap[a64]["section"], q))
    bank_section = {}
    for c, _, _, _, _, bank, _, sec, _ in rows:
        bank_section[(c, sec)] = bank_section.get((c, sec), 0.0) + bank
    rng = np.random.default_rng(seed)
    tape, excluded_share, net_cash, capped = [], [], 0, 0
    for c, div, size, n, turnover, bank, a64, sec, q in rows:
        u = rng.random((2, firms_per_cell))
        u0 = quantile_position(*q[:3], 100 * margin_floor)   # share of firms below the margin floor, excluded
        excluded_share.append(u0)
        margin = quantile_draw(*q[:3], u0 + (1 - u0) * u[0]) / 100
        x = quantile_draw(100 / q[5], 100 / q[4], 100 / q[3], u[1])  # net debt / gross operating profit
        net_cash += int((x <= 0).sum())
        capped += int((x > leverage_cap).sum())
        x = np.minimum(x, leverage_cap)
        revenue = turnover * 1e3 / n
        exposure = cq5.get((c, sec), 0.0) * 1e6 * bank / bank_section[(c, sec)] / firms_per_cell
        for k in range(firms_per_cell):
            ebitda = margin[k] * revenue
            tape.append({"loan_id": f"{c}-{div}-{size}-{k}", "firm_id": f"{c}-{div}-{size}-{k}", "country": c,
                         "nace": a64, "size_class": BACH_SIZES[size], "revenue": revenue, "ebitda": ebitda,
                         "financial_debt": ebitda * x[k] if x[k] > 0 else 0.0, "exposure": exposure,
                         "ghg_t": e0[(c, a64)] * revenue})
    covered = set(bank_section)
    tape += [r for r in rep if (r["country"], smap[r["nace"]]["section"]) not in covered]
    stats = {"bach_cells": len(rows), "bach_firms": len(rows) * firms_per_cell, "mean_share_below_margin_floor": float(np.mean(excluded_share)),
             "net_cash_draws": net_cash, "leverage_capped_draws": capped, "sections_from_representative_firm": sorted(
                 {f'{r["country"]}-{smap[r["nace"]]["section"]}' for r in rep
                  if (r["country"], smap[r["nace"]]["section"]) not in covered})}
    return tape, smap, stats


def to_arrays(tape, smap, raw):
    """Firm arrays for the engine."""
    dam = damodaran(raw)
    mult, sig = {k: v[0] for k, v in dam.items()}, {k: v[1] for k, v in dam.items()}
    d = [smap[r["nace"]]["damodaran_industry"] for r in tape]
    f = {
        "country": np.array([r["country"] for r in tape]),
        "nace": np.array([r["nace"] for r in tape]),
        "section": np.array([smap[r["nace"]]["section"] for r in tape]),
        "iam_sector": [smap[r["nace"]]["iam_sector"] for r in tape],
        "e0": np.array([r["ghg_t"] / r["revenue"] for r in tape]),
        "margin": np.array([r["ebitda"] / r["revenue"] for r in tape]),
        "mult": np.array([mult[x] for x in d]),
        "sigma": np.array([sig[x] for x in d]),
        "exposure": np.array([r["exposure"] for r in tape]),
    }
    # Net debt <= 0 (net cash): no default barrier, V/D infinite, PD 0.
    f["v_over_d"] = f["mult"] * np.array([r["ebitda"] / r["financial_debt"] if r["financial_debt"] > 0 else np.inf
                                          for r in tape])
    return f
