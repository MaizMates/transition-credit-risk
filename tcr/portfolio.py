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
    f["v_over_d"] = f["mult"] * np.array([r["ebitda"] / r["financial_debt"] for r in tape])
    return f
