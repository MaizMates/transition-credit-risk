"""python run.py config.toml  ->  results/"""
import csv
import hashlib
import json
import sys
import tomllib
from pathlib import Path

import numpy as np

from tcr import engine, portfolio, report, scenarios

ROOT = Path(__file__).parent
RAW, REF, OUT = ROOT / "data" / "raw", ROOT / "data" / "ref", ROOT / "results"


def anchors(path):
    """Obligor-weighted mean historical default rate per country, PD ranges excluding default (EU CR9)."""
    acc = {}
    for r in csv.DictReader(open(path)):
        n = int(r["obligors"])
        a = acc.setdefault(r["country"], [0.0, 0])
        a[0] += n * float(r["hist_default_rate_pct"]) / 100
        a[1] += n
    return {c: s / n for c, (s, n) in acc.items()}


def simulate(firms, paths, anchor, pi, k_repl, sigma_scale, unpriced=()):
    """PD[i,t] per (country, scenario), with c calibrated per country x section at t0."""
    firms = {**firms, "priced": np.array([s not in unpriced for s in firms["iam_sector"]])}
    sigma = firms["sigma"] * sigma_scale
    dd0 = engine.distance_to_default(firms["v_over_d"][:, None], sigma)[:, 0]
    c = np.zeros(len(dd0))
    for key in {(a, b) for a, b in zip(firms["country"], firms["section"])}:
        i = (firms["country"] == key[0]) & (firms["section"] == key[1])
        c[i] = engine.calibrate(dd0[i], firms["exposure"][i], anchor[key[0]])
    out, nonpos = {}, 0
    for (country, s), sc in paths.items():
        i = firms["country"] == country
        sub = {k: (v[i] if isinstance(v, np.ndarray) else [x for x, keep in zip(v, i) if keep]) for k, v in firms.items()}
        m, vd = engine.project(sub, sc, pi, k_repl)
        nonpos += int((m <= 0).sum())
        out[(country, s)] = engine.pd(m, vd, sigma[i], c[i])
    return out, nonpos


def aggregate(firms, pds, grid, ref_scen, lgd):
    port, sect = [], []
    for (country, s), p in pds.items():
        i = firms["country"] == country
        w, sec = firms["exposure"][i], firms["section"][i]
        base = pds[(country, ref_scen)]
        for t, y in enumerate(grid):
            port.append({"country": country, "scenario": s, "year": int(y), "pd": float(np.average(p[:, t], weights=w)),
                         "dpd_pp": float(100 * np.average(p[:, t] - base[:, t], weights=w)),
                         "el_eur_m": float((p[:, t] * lgd * w).sum() / 1e6)})
            for k in sorted(set(sec)):
                j = sec == k
                sect.append({"country": country, "section": k, "scenario": s, "year": int(y),
                             "pd": float(np.average(p[j, t], weights=w[j])),
                             "dpd_pp": float(100 * np.average(p[j, t] - base[j, t], weights=w[j]))})
    return port, sect


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(cfg_path):
    cfg = tomllib.loads(Path(cfg_path).read_text())
    run, conv, sens = cfg["run"], cfg["conversion"], cfg["sensitivity"]
    OUT.mkdir(exist_ok=True)
    grid = np.arange(run["base_year"], run["end_year"] + 1)
    eur = conv["deflator_base"] / conv["deflator_2010"] / conv["usd_per_eur_2010"]

    tape, smap = portfolio.representative_tape(RAW, REF, run["countries"], run["v_over_d"])
    ok, rejected = portfolio.validate(tape, run["countries"], set(smap))
    firms = portfolio.to_arrays(ok, smap, RAW)
    exp_in = sum(np.nan_to_num(r["exposure"]) for r in tape)
    exp_out = firms["exposure"].sum() + sum(np.nan_to_num(r["exposure"]) for r in rejected)
    assert abs(exp_in - exp_out) < 1e-6 * exp_in, "exposure reconciliation failed"
    anchor = anchors(REF / "cr9_rows.csv")

    def variant(model, pi=run["pass_through"], sigma_scale=1.0, unpriced=tuple(run["unpriced_sectors"])):
        paths, skipped = scenarios.load(RAW / "ngfs_phase5.csv", model, run["countries"], grid, eur)
        pds, nonpos = simulate(firms, paths, anchor, pi, run["k_repl"], sigma_scale, unpriced)
        return aggregate(firms, pds, grid, run["reference_scenario"], run["lgd"]), skipped, nonpos

    (port, sect), skipped, nonpos = variant(run["reference_iam"])
    report.write_csv(port, OUT / "pd_portfolio.csv")
    report.write_csv(sect, OUT / "pd_by_sector.csv")
    if rejected:
        report.write_csv(rejected, OUT / "rejected.csv")

    def nz2050(rows, label):
        return [{"variant": label, "country": r["country"], "dpd_pp": r["dpd_pp"], "pd": r["pd"]} for r in rows
                if r["scenario"] == "Net Zero 2050" and r["year"] == run["end_year"]]

    sens_rows = nz2050(port, "Reference")
    for p in sens["pass_through"]:
        sens_rows += nz2050(variant(run["reference_iam"], pi=p)[0][0], f"Pass-through {p:.0%}")
    for s in sens["sigma_scale"]:
        sens_rows += nz2050(variant(run["reference_iam"], sigma_scale=s)[0][0], f"Volatility x{s}")
    for u in sens["unpriced_sectors"]:
        sens_rows += nz2050(variant(run["reference_iam"], unpriced=(u,))[0][0], f"{u} unpriced")
    for m in sens["iams"]:
        sens_rows += nz2050(variant(m)[0][0], m.split(" ")[0].split("-")[0])
    report.write_csv(sens_rows, OUT / "sensitivity.csv")

    report.heatmap([r for r in sect if r["year"] in (2030, 2040, 2050) and r["scenario"] != run["reference_scenario"]
                    and r["scenario"] in run["chart_scenarios"]], run["countries"],
                   [s for s in run["chart_scenarios"] if s != run["reference_scenario"]], [2030, 2040, 2050],
                   OUT / "chart_pd_shift_by_sector.png")
    report.paths(port, run["countries"], run["chart_scenarios"], OUT / "chart_portfolio_pd_path.png")
    report.sensitivity(sens_rows, run["countries"], OUT / "chart_sensitivity.png")

    manifest = {
        "config_sha256": sha256(cfg_path),
        "inputs_sha256": {p.name: sha256(p) for p in sorted(RAW.glob("*.csv")) + sorted(REF.glob("*.csv"))},
        "ngfs": "NGFS Phase V, IIASA Scenario Explorer ngfs_phase_5",
        "eur_per_usd2010_at_2023_prices": eur,
        "anchors_pd": anchor,
        "loans_valid": len(ok), "loans_rejected": len(rejected),
        "projection_cells_with_ebitda_le_0": nonpos,
        "scenarios_skipped": skipped,
        "exposure_eur_m": {"in": exp_in / 1e6, "valid": float(firms["exposure"].sum() / 1e6)},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: manifest[k] for k in ("anchors_pd", "loans_valid", "loans_rejected",
                                                "projection_cells_with_ebitda_le_0", "scenarios_skipped")}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "config.toml")
