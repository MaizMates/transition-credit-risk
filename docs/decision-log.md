# Decision log: verification of sources and deviations from the design spec

Date: 2026-09-29. Each row records what was checked, what was found and what was decided.

| Item | Finding | Decision |
|---|---|---|
| NGFS licence | Use allowed for research and commercial purposes; "restricts redistribution of substantial parts of the data" (https://zenodo.org/records/15790097) | Repo ships the download script, never the data; publish only aggregated results and charts |
| NGFS access | pyam `read_iiasa('ngfs_phase_5')`, guest access; needs `sqlalchemy<2.1` (ixmp4 0.16.10 breaks on 2.1.1) | pyam used only in the download script |
| Reference IAM | Regions: GCAM EU-15, REMIND EU 28, MESSAGEix Western Europe | GCAM 6.0 NGFS (finest region with IT and DE) |
| Carbon price | `Price|Carbon`, US$2010/t CO2; identical in EU-15, ITA, DEU; 0 in Current Policies (price above current policies). GCAM Net Zero 2050: 21.2 (2025), 80.9 (2030), 381.3 (2040), 1581.4 (2050) | Use as-is; Current Policies is the reference |
| Sector emissions | Country level (Downscaling[GCAM]) for Industry, Industrial Processes, Transportation, Residential and Commercial; EU-15 only for Electricity, Energy Supply, AFOLU | Country level where available, EU-15 otherwise; agriculture uses `Emissions|CH4|AFOLU` (CO2 AFOLU can be negative) |
| GDP | NiGEM: level only in Baseline (2017 PPP US$ bn); scenarios as `Gross Domestic Product (GDP)(transition)`, % difference from Baseline; Current Policies not reported | GDP = Baseline x (1 + delta/100); Current Policies delta = 0 (assumption, state in note) |
| Physical damages | Kotz et al. (2024), basis of Phase V chronic damages, reported retracted (to confirm at source) | Transition-only GDP variant; chronic damages excluded |
| Eurostat | SDMX-CSV API works without login: env_ac_ainah_r2 (freq, airpol, nace_r2, unit, geo), nama_10_a64 (freq, unit, nace_r2, na_item, geo). Example DE C23 2023: 29,270.8 kt GHG / 58,539 MEUR output | Intensity = GHG THS_T / P1 CP_MEUR, year 2023 |
| Damodaran | `optvarEurope.xls` (std dev of firm value) and `vebitdaEurope.xls` (EV/EBITDA, positive-EBITDA firms and all firms), updated January 2026 | Europe datasets, no global fallback; use "Only positive EBITDA firms" multiple |

Still open: BACH download route, CR9 anchors (two IRB banks per country), Banca d'Italia and Destatis sector rates, IMF (2019) replacement cost, USD/EUR 2010 and deflator.

## Decisions after the draft spec (2026-09-29)

| Item | Decision | Reason |
|---|---|---|
| Portfolio | Representative-firm mode: one loan per country x A64 industry (Eurostat 2023) | BACH requires a registered login; leverage cancels in this mode |
| Margin | (B1G - D1 - D29X39) / P1 from nama_10_a64 | B2A3G not published in nama_10_a64; same denominator as emission intensity |
| Exposure weights | Pillar 3 EU CQ5 at 31 Dec 2025: Intesa Sanpaolo (IT), Deutsche Bank (DE); sections K, O excluded | Public bank-book sector mix; AnaCredit by NACE not available via ECB API |
| Anchor class | CR9 "Corporates - Other" / "General" (CRR3 classes), not "Corporates - SME" | CRR3 templates (Reg. 2024/3172) no longer separate corporate SMEs |
| Anchor values | IT 1.69% (Intesa, UniCredit), DE 0.39% (Deutsche Bank, DZ BANK) | DE historical column = 2025 observed (CRR3 phase-in, DB p.139) |
| Sector relatives | Not used in v1: uniform anchor within country | Banca d'Italia and Destatis extraction left for v2 |
| k_repl | 0, no sensitivity value | OP 281 value not reported; IMF (2019) article gives per-technology costs only |
| Negative IAM emissions | Ratio floored at 0 | CCS/removals make net sector emissions negative; would create carbon revenue |
| AFOLU pricing | Priced by default; sensitivity with AFOLU unpriced | Drives most of the Italian portfolio result |
| Damodaran multiple | First "EV/EBITDA" column (positive-EBITDA firms) | File has two columns with the same name |

## BACH firm-level mode (2026-10-03)

| Item | Decision | Reason |
|---|---|---|
| Source | BACH full database, release 14 Sep 2026 (`bach.zip`, file `20260914.csv`), year 2023, variable sample, size classes 1a/1b/2, divisions | Free registration; 2023 has the widest IT and DE coverage |
| Margin | R32 (gross operating profit / net turnover), drawn above the 0.5% floor | Floor-truncation would create artificial near-zero-margin firms; mean 8.6% of firms per cell excluded |
| Leverage | Net debt / gross operating profit = 1 / R27, quartiles mapped exactly; cells with R27 Q1 <= 0 excluded | R27 is unstable near zero net debt; linear interpolation of R27 produced unbounded leverage |
| Leverage cap | 20x (11.8% of draws), sensitivities 10x and 40x | Without a cap the calibration puts all default risk in the tail (DE section Q failed to calibrate); ECB leveraged-transactions guidance (2017) treats > 6x as highly leveraged |
| Net cash | Net debt <= 0 gives no default barrier, PD 0 (6.7% of draws) | Merton barrier undefined |
| Exposure | CQ5 section split across cells by BACH L2 (amounts owed to credit institutions) | Bank-debt weights within section |
| Fallback | Sections without usable BACH cells keep the representative firm: DE A, B, E, I; IT P, Q | Coverage gaps in BACH 2023 |
| Calibration bracket | Brent on [-20, 20]; failure names country and section | Spec section 9 |

## Sector relatives (2026-10-04)

| Item | Decision | Reason |
|---|---|---|
| Germany | Anchor x relative factor from Destatis insolvency frequency, 2021-2025 mean, normalised to exposure-weighted mean 1 | Gives sector-specific starting PDs without changing the Pillar 3 level |
| Denominator | Legal units in the Destatis business register of year t-1 | 2025 register unpublished; reproduces official 2025 rates within 4% |
| Agriculture (DE) | Average factor | Not in the Destatis register |
| Italy | Uniform anchor | Banca d'Italia moved ATECO-level default series to its online database (no programmatic access found); PDF has broad sectors only |
| Access | GENESIS API with a personal token kept in `.env.local` (ignored by git) | Destatis requires free registration for API access |
