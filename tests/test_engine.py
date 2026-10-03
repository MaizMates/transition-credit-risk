import math

import numpy as np
from scipy.stats import norm

from tcr import engine, portfolio, scenarios

T = 5


def firm(e0=5e-4, margin=0.10, sigma=0.3, v_over_d=1.5, mult=8.0, sector="IND"):
    return {"e0": np.array([e0]), "margin": np.array([margin]), "sigma": np.array([sigma]),
            "v_over_d": np.array([v_over_d]), "mult": np.array([mult]), "iam_sector": [sector]}


def path(P, gdp=None, E=None):
    return {"P": np.asarray(P, float), "gdp": np.ones(T) if gdp is None else np.asarray(gdp, float),
            "E": {"IND": np.ones(T) if E is None else np.asarray(E, float)}}


def test_merton_pd_matches_hand_computation():
    # V/D = 1.5, sigma = 0.3, c = 0: DD = (ln 1.5 - 0.045) / 0.3
    dd = (math.log(1.5) - 0.3 ** 2 / 2) / 0.3
    p = engine.pd(np.array([[0.1]]), np.array([[1.5]]), np.array([0.3]), np.array([0.0]))
    assert abs(p[0, 0] - norm.cdf(-dd)) < 1e-12
    assert abs(p[0, 0] - 0.1148) < 1e-4  # DD = 1.2016


def test_calibration_hits_anchor():
    dd0 = np.array([0.5, 1.0, 2.0])
    w = np.array([1.0, 2.0, 3.0])
    c = engine.calibrate(dd0, w, 0.017)
    assert abs(np.average(norm.cdf(-(dd0 + c)), weights=w) - 0.017) < 1e-6


def test_pd_constant_with_flat_carbon_price_and_gdp():
    f = firm()
    m, vd = engine.project(f, path(np.full(T, 50.0)))
    p = engine.pd(m, vd, f["sigma"], np.array([0.0]))
    assert np.allclose(p, p[:, :1])


def test_higher_carbon_price_never_lowers_pd():
    f = firm()
    low = engine.pd(*engine.project(f, path(np.linspace(0, 100, T))), f["sigma"], np.array([0.0]))
    high = engine.pd(*engine.project(f, path(np.linspace(0, 300, T))), f["sigma"], np.array([0.0]))
    assert np.all(high >= low)
    assert high[0, -1] > low[0, -1]


def test_negative_iam_emissions_do_not_create_carbon_revenue():
    f = firm()
    base = engine.project(f, path(np.zeros(T)))[0]
    m, _ = engine.project(f, path(np.linspace(0, 500, T), E=[1, 0.5, 0, -0.5, -1]))
    assert np.all(m <= base + 1e-12)


def test_ebitda_wiped_out_gives_pd_one():
    f = firm(e0=1e-3, margin=0.05)            # break-even at +50 EUR/t
    m, vd = engine.project(f, path([0, 25, 50, 75, 100]))
    p = engine.pd(m, vd, f["sigma"], np.array([0.0]))
    assert p[0, -1] == 1.0 and p[0, 1] < 1.0


def test_annual_interpolation_keeps_five_year_points():
    grid = np.arange(2025, 2051)
    years, vals = [2020, 2025, 2030, 2035, 2040, 2045, 2050], [0, 10, 40, 90, 160, 250, 360]
    out = scenarios.annual(years, vals, grid)
    for y, v in zip(years[1:], vals[1:]):
        assert out[y - 2025] == v
    assert out[2027 - 2025] == 22.0


def test_interpolation_refuses_to_extrapolate():
    try:
        scenarios.annual([2030, 2050], [1, 2], np.arange(2025, 2051))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_loan_tape_validation_rules():
    good = {"loan_id": "1", "firm_id": "f", "country": "IT", "nace": "C23", "size_class": "small",
            "revenue": 10.0, "ebitda": 1.0, "financial_debt": 5.0, "exposure": 3.0}
    rows = [good, {**good, "loan_id": "1"}, {**good, "loan_id": "2", "ebitda": -1.0},
            {**good, "loan_id": "3", "country": "FR"}, {**good, "loan_id": "4", "nace": "Z99"},
            {**good, "loan_id": "5", "exposure": -1.0}, {**good, "loan_id": "6", "revenue": float("nan")}]
    ok, rej = portfolio.validate(rows, ["IT", "DE"], {"C23"})
    assert [r["loan_id"] for r in ok] == ["1"]
    assert [r["rule"] for r in rej] == ["loan_id not unique", "ebitda <= 0 (Merton asset value undefined)",
                                        "country not in scope", "nace not mapped", "negative debt or exposure",
                                        "missing amount"]


def test_bach_quantile_draw_and_inverse():
    q = (2.0, 10.0, 30.0)
    assert np.allclose(portfolio.quantile_draw(*q, np.array([0.25, 0.5, 0.75])), q)
    for v in (5.0, 10.0, 20.0):
        u = portfolio.quantile_position(*q, v)
        assert abs(portfolio.quantile_draw(*q, np.array([u]))[0] - v) < 1e-9


def test_a64_codes_cover_bach_divisions():
    assert portfolio.covers("C10-C12", "C11") and portfolio.covers("C31_C32", "C32")
    assert portfolio.covers("B", "B06") and portfolio.covers("C23", "C23")
    assert not portfolio.covers("C10-C12", "C13") and not portfolio.covers("C23", "C24")
