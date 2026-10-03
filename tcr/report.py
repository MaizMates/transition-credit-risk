"""CSV outputs and the three charts."""
import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]          # reference categorical slots 1-3
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
SEQUENTIAL = LinearSegmentedColormap.from_list("seq", ["#f0efec", "#86b6ef", "#2a78d6", "#184f95"])
SECTION_NAMES = {"A": "Agriculture", "B": "Mining", "C": "Manufacturing", "D": "Electricity, gas", "E": "Water, waste",
                 "F": "Construction", "G": "Trade", "H": "Transport", "I": "Accommodation, food", "J": "ICT",
                 "L": "Real estate", "M": "Professional services", "N": "Administrative services", "P": "Education",
                 "Q": "Health", "R": "Arts, recreation", "S": "Other services"}
SHORT = {"Net Zero 2050": "NZ", "Delayed transition": "DT", "Current Policies": "CP"}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def heatmap(sector_rows, countries, scenarios, years, path):
    """Change in PD (pp) versus Current Policies by NACE section, scenario and year, one panel per country."""
    fig, axes = plt.subplots(1, len(countries), figsize=(11, 6.5), sharey=True)
    sections = sorted({r["section"] for r in sector_rows})
    cols = [(s, y) for s in scenarios for y in years]
    vals = {(r["country"], r["section"], r["scenario"], r["year"]): r["dpd_pp"] for r in sector_rows}
    data = {c: np.array([[vals.get((c, sec, s, y), np.nan) for s, y in cols] for sec in sections]) for c in countries}
    for ax, c in zip(np.atleast_1d(axes), countries):
        im = ax.imshow(np.clip(data[c], 0, None), cmap=SEQUENTIAL, norm=Normalize(0, 10), aspect="auto")
        for i in range(len(sections)):
            for j in range(len(cols)):
                v = data[c][i, j]
                if abs(v) >= 0.01:
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                            color="#ffffff" if v > 6 else INK)
        ax.set_xticks(range(len(cols)), [f"{SHORT.get(s, s)} {y}" for s, y in cols], fontsize=7)
        ax.set_yticks(range(len(sections)), [f"{k} {SECTION_NAMES.get(k, '')}" for k in sections])
        ax.set_title(c, loc="left", fontweight="bold")
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.colorbar(im, ax=axes, shrink=0.6, extend="max", label="PD change vs Current Policies (pp, colour capped at 10)")
    fig.suptitle("Transition-risk PD shift by NACE section vs Current Policies (NGFS Phase V, GCAM; NZ = Net Zero 2050, "
                 "DT = Delayed transition)", x=0.02, ha="left", fontweight="bold", fontsize=10)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def paths(portfolio_rows, countries, scenarios, path):
    """Exposure-weighted portfolio PD over time per scenario, one panel per country."""
    fig, axes = plt.subplots(1, len(countries), figsize=(10, 3.8), sharey=False)
    for ax, c in zip(np.atleast_1d(axes), countries):
        for col, s in zip(SERIES, scenarios):
            rows = [r for r in portfolio_rows if r["country"] == c and r["scenario"] == s]
            x = [r["year"] for r in rows]
            y = [100 * r["pd"] for r in rows]
            ax.plot(x, y, color=col, lw=2, label=s)
        ax.set_title(c, loc="left", fontweight="bold")
        ax.set_ylabel("Portfolio PD (%)")
        ax.grid(axis="y", color="#e4e3df", lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    np.atleast_1d(axes)[0].legend(frameon=False, fontsize=7, loc="upper left")
    fig.suptitle("Portfolio PD path, exposure-weighted (NGFS Phase V, GCAM)", x=0.02, ha="left", fontweight="bold")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def sensitivity(sens_rows, countries, path):
    """2050 portfolio PD change vs Current Policies under Net Zero 2050, by variant."""
    variants = list(dict.fromkeys(r["variant"] for r in sens_rows))
    fig, ax = plt.subplots(figsize=(max(9, 1.1 * len(variants)), 4.2))
    w = 0.8 / len(countries)
    for k, (c, col) in enumerate(zip(countries, SERIES)):
        vals = [next(r["dpd_pp"] for r in sens_rows if r["variant"] == v and r["country"] == c) for v in variants]
        xs = np.arange(len(variants)) + (k - (len(countries) - 1) / 2) * w
        ax.bar(xs, vals, width=w - 0.02, color=col, label=c)
        for x, v in zip(xs, vals):
            ax.text(x, v, f"{v:.2f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7, color=INK2)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(range(len(variants)), variants, fontsize=7, rotation=25, ha="right")
    ax.set_ylabel("PD change 2050 (pp)")
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("Sensitivity: Net Zero 2050 vs Current Policies, portfolio PD change in 2050", loc="left", fontweight="bold")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
