"""Projection of firm financials (three channels) and Merton PD with calibration."""
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def project(firms, sc, pi=0.0, k_repl=0.0):
    """Margin path m[i,t] and asset-to-debt ratio V/D[i,t] for one country-scenario path."""
    g = sc["gdp"]
    # Net IAM emissions turn negative with CCS/removals; a firm's Scope 1 cost cannot, so floor at zero.
    E = np.maximum(np.vstack([sc["E"][s] for s in firms["iam_sector"]]), 0.0)
    e = firms["e0"][:, None] * E / g[None, :]                 # tonnes CO2e per EUR of revenue
    dP = sc["P"] - sc["P"][0]                                  # EUR per tonne above base year
    margin = firms["margin"][:, None]
    priced = firms.get("priced", np.ones(len(margin), bool))[:, None]
    m = margin - (1 - pi) * dP[None, :] * e * priced           # EBITDA / revenue
    abated = np.maximum(0.0, -np.diff(e, axis=1, prepend=e[:, :1]))
    rev0_over_d0 = firms["v_over_d"] / (firms["mult"] * firms["margin"])
    invest = np.cumsum(abated * k_repl * g[None, :], axis=1)  # cumulative abatement capex / revenue_0
    # D_t / D_0; firms with no net debt (V/D infinite) only add debt if they invest.
    with np.errstate(invalid="ignore"):
        debt = g[None, :] + np.where(invest > 0, invest * rev0_over_d0[:, None], 0.0)
    vd = firms["v_over_d"][:, None] * (m / margin) * g[None, :] / debt
    return m, vd


def distance_to_default(vd, sigma):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.log(vd) - sigma[:, None] ** 2 / 2) / sigma[:, None]


def pd(m, vd, sigma, c):
    """Merton PD, T = 1, drift 0; EBITDA <= 0 gives PD = 1."""
    p = norm.cdf(-(distance_to_default(vd, sigma) + c[:, None]))
    return np.where(m <= 0, 1.0, p)


def calibrate(dd0, weights, anchor):
    """Constant c such that the weighted mean PD at t0 equals the anchor."""
    f = lambda c: np.average(norm.cdf(-(dd0 + c)), weights=weights) - anchor
    return brentq(f, -20, 20)
