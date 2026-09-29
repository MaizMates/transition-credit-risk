# Transition credit risk engine: design

Date: 2026-09-28. Owner: Marco Izzo. Status: implemented as v1 on 2026-09-29; deviations logged in docs/week1-verification.md.

## 1. Purpose

A transparent, reproducible engine that translates NGFS Phase V transition scenarios into
probabilities of default (PD) and expected loss (EL) for a bank's non-financial corporate loan
book, by sector and country, over 2025-2050.

It serves one goal: a public demonstration of climate credit-risk modelling that team leads in
bank risk functions and consultancy risk practices can inspect in minutes. The product is the
engine. The synthetic portfolio exists only for the demo; a bank can load its own loan tape.

Decisions taken by Marco during brainstorming:

| Decision | Choice | Date |
|---|---|---|
| Use case | Resilience analysis 2030-2050 on NGFS Phase V | 2026-09-25 |
| PD model | Merton structural model on public data | 2026-09-28 |
| Countries | Italy and Germany | 2026-09-28 |

## 2. Regulatory context

- EBA/GL/2025/04, Guidelines on environmental scenario analysis, published 5 November 2025,
  apply from 1 January 2027. Two pillars: integration of environmental risks into stress
  testing, and resilience analysis over the medium to long term.
  Source: https://www.eba.europa.eu/publications-and-media/press-releases/eba-publishes-its-final-guidelines-environmental-scenario-analysis
- ECB 2022 climate risk stress test: around 60% of banks had no climate stress-testing
  framework; most did not include climate risk in credit risk models.
  Source: https://www.bankingsupervision.europa.eu/press/pr/date/2022/html/ssm.pr220708~565c38d18a.en.html
- ECB Occasional Paper 281 (September 2021), economy-wide climate stress test. The engine
  replicates its transmission channels (section 5.1, Appendix B). It does not replicate its PD
  equation (7), which is estimated on proprietary Moody's CreditEdge PDs.
  Source: https://www.ecb.europa.eu/pub/pdf/scpops/ecb.op281~05a7735b1c.en.pdf

## 3. Scope

In scope (v1):

- Transition risk only, on loans to non-financial corporations (SME and corporate).
- Countries: IT, DE.
- Scenarios: all seven NGFS Phase V scenarios loadable; charts show Net Zero 2050, Delayed
  Transition, Current Policies.
- Horizon: 2025-2050, annual. IAM data (5-year steps) interpolated linearly; NiGEM data annual.
- One reference IAM for the headline results; the other two IAMs as a sensitivity. The
  reference IAM is the one with the finest region containing both IT and DE; ties are broken
  alphabetically. GDP comes from the NiGEM run driven by the same IAM.
- Three transmission channels: direct carbon cost on Scope 1 emissions, debt-financed
  abatement investment, GDP-driven revenue.
- Static balance sheet: exposures constant over the horizon.

Out of scope (v1), candidates for v2: physical risk (collateral LGD channel), energy-cost
channel via Scope 2, revenue channel via Scope 3, IFRS 9 staging and lifetime ECL, challenger
PD model (synthetic rating from interest coverage), dynamic balance sheet.

Deliverables are in English.

## 4. Input: loan tape schema

One row per loan. All amounts in EUR, base-year prices.

| Column | Type | Rule |
|---|---|---|
| loan_id | text | unique |
| firm_id | text | not null |
| country | text | IT or DE |
| nace | text | NACE Rev. 2 division, section letter plus two digits (e.g. C23) |
| size_class | text | small, medium, large (BACH size classes) |
| revenue | double | > 0 |
| ebitda | double | > 0 (the Merton asset value is undefined otherwise) |
| financial_debt | double | >= 0 |
| exposure | double | >= 0 (EAD) |

Rows that fail a rule are written to `results/rejected.csv` with the rule that failed. They are
never dropped silently.

## 5. Method

Indices: firm i, country c, NACE division j, NACE section k, IAM emission sector m, scenario s,
year t. Base year t0 = 2025.

### 5.1 Projection of firm financials

```
Revenue[i,s,t]  = Revenue[i,t0] * GDP[c,s,t] / GDP[c,s,t0]
e[i,s,t]        = e[j,c] * (E[m,s,t] / E[m,s,t0]) / (GDP[c,s,t] / GDP[c,s,t0])
EBITDA[i,s,t]   = margin[i] * Revenue[i,s,t]
                  - (1 - pi) * (P[s,t] - P[s,t0]) * e[i,s,t] * Revenue[i,s,t]
Invest[i,s,t]   = max(0, e[i,s,t-1] - e[i,s,t]) * Revenue[i,s,t] * k_repl,   Invest[i,s,t0] = 0
Debt[i,s,t]     = Debt[i,t0] * Revenue[i,s,t] / Revenue[i,t0] + sum_{u<=t} Invest[i,s,u]
```

- GDP: NiGEM real GDP for the country, per scenario, from the NiGEM run of the reference IAM.
- e[j,c]: Scope 1 intensity, tonnes CO2e per EUR of output, of the A64 industry containing
  division j, from Eurostat air emissions accounts divided by output from national accounts,
  latest common year.
- E[m,s,t]: CO2 emissions of the IAM sector m mapped to division j (mapping in
  `data/ref/nace_map.csv`), for the IAM region containing country c.
- P[s,t]: IAM carbon price, converted from US$2010 per tonne to EUR of the base year (section
  7.2). Using P minus P at t0 keeps the 2025 baseline equal across scenarios; carbon costs
  already paid in 2025 sit in observed margins.
- pi: cost pass-through share. Default 0; sensitivity 0.5.
- k_repl: replacement cost per tonne of CO2 abated, IMF (2019) as cited in OP 281 Appendix B.
- margin[i] = EBITDA[i,t0] / Revenue[i,t0]. Capital structure constant apart from abatement
  debt, as in OP 281 Appendix B step 5.

### 5.2 Merton PD

```
V[i,s,t]   = mult[j] * EBITDA[i,s,t]
DD[i,s,t]  = (ln(V / Debt) - sigma[j]^2 / 2) / sigma[j]          (T = 1, drift 0)
PD[i,s,t]  = Phi(-(DD[i,s,t] + c[c,k]))
```

- mult[j]: EV/EBITDA of the Damodaran Europe industry mapped to division j
  (`data/ref/damodaran_map.csv`).
- sigma[j]: firm-value volatility of the same Damodaran industry.
- Rules in projection years: EBITDA <= 0 gives PD = 1; Debt = 0 gives PD = 0. Both counts are
  reported per run. At t0 every loan has EBITDA > 0 by validation (section 4), so the
  calibration in 5.3 always has finite distances to default.

### 5.3 Calibration

c[c,k] is solved per country and NACE section with Brent's method on [-10, 10] so that the
exposure-weighted mean PD at t0 equals the anchor:

```
anchor[c,k] = DR[c] * r[c,k]
r[c,k]      = rate[c,k] / rate[c,all]
```

- DR[c]: level. Obligor-weighted mean of the "average historical annual default rate" in the
  row "Corporates - SME" of Pillar 3 template EU CR9, for the two largest IRB banks by
  consolidated total assets, at the same reporting date, in country c that disclose that row. Regulatory default definition, Article 178 CRR,
  identical in both countries.
- rate[c,k]: sector relatives only, averaged over the latest five available years.
  IT: Banca d'Italia deterioration rates of loans to non-financial corporations by ATECO branch
  (https://www.bancaditalia.it/pubblicazioni/condizioni-rischiosita/STACORIS_note-met.pdf).
  DE: Destatis insolvencies per 10,000 enterprises by WZ 2008 section
  (https://genesis.destatis.de/datenbank/online/statistic/52411/).
  National statistics are not used for the level: insolvency is a narrower event than default
  (the highest German sector rate is 12.7 per 10,000, i.e. 0.127%).
- ATECO 2025 (Banca d'Italia from February 2026) is mapped to NACE Rev. 2 sections through the
  official correspondence table.
- If Brent's method does not converge, the run stops and names the country and section.

### 5.4 Aggregation and loss

```
PD_agg  = sum(PD * exposure) / sum(exposure)        by country, section, scenario, year
EL      = sum(PD * LGD * exposure),  LGD = 40%
```

LGD 40%: F-IRB senior unsecured exposures to corporates, Article 161(1) CRR as amended by
Regulation (EU) 2024/1623. Exposure-weighted aggregation follows OP 281 section 6.1.1. Results
are reported as levels and as differences to Current Policies.

### 5.5 Sensitivities

pi in {0, 0.5}; IAM in {GCAM, MESSAGEix-GLOBIOM, REMIND-MAgPIE}; sigma scaled by {0.8, 1.2}.

## 6. Synthetic portfolio (demo input)

- Source: BACH, harmonised company accounts by country, NACE division and size class, with
  quartiles of financial ratios (https://www.eccbso.org/wba/databases).
- Per country, N firms (config, default 10,000) allocated to division x size cells in
  proportion to the cell's amounts owed to credit institutions.
- Per firm, each ratio is drawn independently from a piecewise-linear quantile function through
  BACH Q1, median and Q3, extended linearly beyond the quartiles and clipped to economically
  valid ranges. Ratios: EBITDA margin (gross operating profit / net turnover), financial debt /
  total assets, net turnover / total assets, amounts owed to credit institutions / total assets.
- Revenue scale: cell net turnover / number of firms in the cell. Exposure: amounts owed to
  credit institutions, capped at financial debt.
- EBITDA margin draws are truncated below at 0.5% so that every synthetic loan passes the
  t0 rule EBITDA > 0; the share of draws truncated is reported in the manifest.
- Fixed random seed in the config.

## 7. Data sources

### 7.1 Sources and status

| Data | Source | Status |
|---|---|---|
| Carbon price, sector emissions, GDP | NGFS Phase V, IIASA Scenario Explorer, IAMC format, guest access | Access verified; licence not verified |
| Company ratios by NACE and size | BACH | Verified |
| Scope 1 intensity by industry | Eurostat air emissions accounts and national accounts by NACE A64 | Dataset codes to verify |
| EV/EBITDA, firm-value volatility | Damodaran Online (https://pages.stern.nyu.edu/~adamodar/pc/archives/data.html) | Europe multiples verified; Europe volatility to verify |
| Default rate level | Pillar 3 EU CR9 of IRB banks | To collect by hand |
| Sector relatives | Banca d'Italia; Destatis GENESIS 52411 | Series verified to exist |
| LGD | Article 161 CRR (CRR3) | Verified |
| Replacement cost per tonne | IMF (2019) via OP 281 | Value to verify |
| USD/EUR 2010, deflator | ECB reference rates; Eurostat HICP or GDP deflator | To verify |

Every row of every file in `data/ref/` carries `source`, `url` and, for documents, `page`.

### 7.2 Week-1 verification tasks and fallback rules

| Open item | Fallback if it fails |
|---|---|
| NGFS licence and terms of use | If redistribution of derived data is not allowed, publish code and charts only, no scenario-derived tables; Marco confirms before publication |
| Damodaran Europe firm-value volatility | Use the Damodaran global dataset and state it in the note |
| Eurostat dataset codes and latest common year | None needed: the data exist; fix codes and year in config |
| IMF (2019) replacement cost | If the value cannot be traced to the IMF source, set k_repl = 0 by default and show the channel only in sensitivities |
| CR9 banks, two per country | Selection rule in 5.3; record bank, report date and page |
| Carbon price unit conversion | US$2010 to EUR2010 at the ECB 2010 average reference rate, then to base-year EUR with the euro area deflator; both values sourced in config |
| IAMC variable names and IAM regions for IT and DE | Fix from the Scenario Explorer variable list; record in `nace_map.csv` |

## 8. Architecture

```
transition-credit-risk/
  config.toml          scenarios, IAM, countries, years, pi, seed, paths, unit conversion
  data/raw/            original downloads (not versioned) and download scripts
  data/ref/            hand-curated tables with sources: anchors.csv, nace_map.csv, damodaran_map.csv
  tcr/scenarios.py     IAMC files to (scenario, year, country, variable, value); annual interpolation
  tcr/sectors.py       NACE to Scope 1 intensity, IAM sector, Damodaran industry
  tcr/portfolio.py     loan tape schema validation; synthetic generator from BACH
  tcr/engine.py        projection (three channels), Merton PD, calibration
  tcr/report.py        aggregates, EL, charts, CSV for Tableau
  run.py               python run.py config.toml
  tests/test_engine.py
  docs/technical-note.md
```

Stack: Python 3.11, DuckDB, numpy, scipy, matplotlib. Config read with the standard library
`tomllib`. No pandas, no pyam: DuckDB reads IAMC CSV directly.

Data flow: download scripts write `data/raw/`. `run.py` loads everything into `tcr.duckdb`
(tables `scenarios`, `sectors`, `portfolio`, `results`), runs the engine, and the report writes
`results/`.

Outputs in `results/`: `pd_by_sector.csv`, `pd_portfolio.csv`, `el.csv`, `sensitivity.csv`,
chart PNGs, `rejected.csv`, `manifest.json`. The manifest records the config hash, the SHA-256
of every input file, the NGFS scenario vintage and the counts of EBITDA <= 0 and Debt = 0 cases.

## 9. Error handling

- Loan tape: schema validation at load; failing rows to `rejected.csv` with the rule.
- Missing mapping (a NACE division without intensity or Damodaran industry): the run stops and
  names the code.
- Calibration non-convergence: the run stops and names the country and section.
- Reconciliation: total exposure in equals total exposure out plus rejected exposure, checked
  in the report.

## 10. Tests

One file, `tests/test_engine.py`:

1. Merton PD equals a hand-computed value.
2. After calibration, exposure-weighted PD at t0 equals the anchor within 1e-6.
3. With constant carbon price and flat GDP, PD is constant over time.
4. A higher carbon price never lowers the PD of a firm with positive emissions.
5. Annual interpolation reproduces the IAM values at the 5-year points.
6. Loan tape validation rejects invalid rows with the correct rule.

## 11. Deliverables and timeline

Deliverables:

1. Private repository. It becomes public on GitHub only after Marco confirms.
2. Technical note, 4 pages: method, sources, limitations, results.
3. Three charts: PD change by NACE section at 2030, 2040 and 2050 per scenario, IT versus DE;
   portfolio PD path per scenario; sensitivities.
4. CSV outputs for an optional Tableau Public dashboard.

Timeline (estimate):

| Week | Dates | Work |
|---|---|---|
| 1 | 29 Sep - 2 Oct 2026 | Downloads, reference tables, CR9 collection, verification tasks in 7.2 |
| 2 | 5 - 9 Oct | scenarios.py, sectors.py, portfolio.py |
| 3 | 12 - 16 Oct | engine.py, calibration, tests |
| 4 | 19 - 23 Oct | report.py, charts, sensitivities |
| 5 | 26 - 30 Oct | Technical note, review |

Target publication: first week of November 2026, about eight weeks before EBA/GL/2025/04
applies.

## 12. Limitations stated in the technical note

1. Asset volatility and multiples come from listed peers, applied to SMEs.
2. BACH ratios are drawn independently: correlations between ratios are lost.
3. Loans with EBITDA <= 0 at t0 are rejected, and EBITDA <= 0 in projection years gives PD = 1:
   both conservative simplifications, with counts reported.
4. Base-year financials are taken as 2025 values.
5. Three of the OP 281 channels are omitted in v1 (energy cost, Scope 3 revenue, physical risk).
6. The engine uses public data and public methodology only.
