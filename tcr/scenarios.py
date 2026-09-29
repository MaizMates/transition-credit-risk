"""NGFS Phase V (IAMC long format) -> annual paths per country and scenario."""
import duckdb
import numpy as np

NATIVE = {
    "GCAM 6.0 NGFS": "GCAM 6.0 NGFS|EU-15",
    "MESSAGEix-GLOBIOM 2.0-M-R12-NGFS": "MESSAGEix-GLOBIOM 2.0-R12|Western Europe",
    "REMIND-MAgPIE 3.3-4.8": "REMIND-MAgPIE 3.3-4.8|EU 28",
}
ISO = {"IT": "ITA", "DE": "DEU"}
NIGEM_REGION = {"IT": "NiGEM NGFS v1.24.2|Italy", "DE": "NiGEM NGFS v1.24.2|Germany"}
# IAM emission sector -> (variables summed, level): country = downscaled, native = IAM region
SECTORS = {
    "IND": (["Emissions|CO2|Energy|Demand|Industry", "Emissions|CO2|Industrial Processes"], "country"),
    "TRANS": (["Emissions|CO2|Energy|Demand|Transportation"], "country"),
    "RC": (["Emissions|CO2|Energy|Demand|Residential and Commercial"], "country"),
    "ELEC": (["Emissions|CO2|Energy|Supply|Electricity"], "native"),
    "SUPPLY": (["Emissions|CO2|Energy|Supply"], "native"),
    "AFOLU": (["Emissions|CH4|AFOLU"], "native"),
}


def annual(years, values, grid):
    """Linear interpolation onto an annual grid; refuses to extrapolate."""
    years = np.asarray(years, float)
    if years.min() > grid[0] or years.max() < grid[-1]:
        raise ValueError(f"series covers {years.min():.0f}-{years.max():.0f}, need {grid[0]}-{grid[-1]}")
    order = np.argsort(years)
    return np.interp(grid, years[order], np.asarray(values, float)[order])


def load(path, model, countries, grid, eur_per_usd2010):
    """Return {(country, scenario): {"P": EUR/t, "gdp": ratio to base year, "E": {sector: ratio}}} and skipped scenarios."""
    rows = duckdb.sql(f"select model, scenario, region, variable, year, value from read_csv_auto('{path}')").fetchall()
    series = {}
    for m, s, r, v, y, val in rows:
        series.setdefault((m, s, r, v), ([], []))
        series[(m, s, r, v)][0].append(y)
        series[(m, s, r, v)][1].append(val)

    def get(m, s, r, v):
        return annual(*series[(m, s, r, v)], grid)

    native, down, nigem = NATIVE[model], f"Downscaling[{model}]", f"NiGEM NGFS v1.24.2[{model}]"
    scenarios = sorted({s for (m, s, r, v) in series if m == model and v == "Price|Carbon"} - {"Baseline"})
    out, skipped = {}, []
    for c in countries:
        base_gdp = get(nigem, "Baseline", NIGEM_REGION[c], "Gross Domestic Product (GDP)")
        for s in scenarios:
            key = (nigem, s, NIGEM_REGION[c], "Gross Domestic Product (GDP)(transition)")
            if key in series:
                gdp = base_gdp * (1 + annual(*series[key], grid) / 100)
            elif s == "Current Policies":  # not reported in the transition variant: zero deviation from Baseline
                gdp = base_gdp
            else:
                skipped.append(f"{c}/{s}: no NiGEM transition GDP")
                continue
            E = {}
            for sec, (vars_, level) in SECTORS.items():
                region = ISO[c] if level == "country" else native
                mdl = down if level == "country" else model
                tot = sum(get(mdl, s, region, v) for v in vars_)
                E[sec] = tot / tot[0]
            out[(c, s)] = {"P": get(model, s, native, "Price|Carbon") * eur_per_usd2010, "gdp": gdp / gdp[0], "E": E}
    return out, skipped
