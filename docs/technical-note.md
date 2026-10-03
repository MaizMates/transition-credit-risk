# Translating NGFS transition scenarios into corporate PDs: a transparent engine on public data

Technical note, v1. September 2026. Author: Marco Izzo.

## 1. Purpose and regulatory context

EBA/GL/2025/04 on environmental scenario analysis apply from 1 January 2027. They require institutions to integrate environmental risks into stress testing and to run a resilience analysis over the medium to long term ([EBA, 5 November 2025](https://www.eba.europa.eu/publications-and-media/press-releases/eba-publishes-its-final-guidelines-environmental-scenario-analysis)). In the ECB 2022 climate stress test, around 60% of banks had no climate stress-testing framework and most did not include climate risk in their credit risk models ([ECB, 8 July 2022](https://www.bankingsupervision.europa.eu/press/pr/date/2022/html/ssm.pr220708~565c38d18a.en.html)).

This engine translates NGFS Phase V transition scenarios into probabilities of default (PD) and expected loss (EL) for a non-financial corporate loan book, by NACE sector, for Italy and Germany, over 2025-2050. Every input is public and cited. Every parameter is in one configuration file. Every run writes a manifest with the hash of each input.

## 2. Method

### 2.1 Transmission channels

The channels follow the ECB economy-wide climate stress test (ECB Occasional Paper 281, September 2021, section 5.1 and Appendix B). The PD equation of that paper, eq. (7), is estimated on proprietary Moody's CreditEdge PDs and is not replicated. For firm i in country c, scenario s, year t, with base year t0 = 2025:

```
e[i,s,t]      = e0[i] * max(E[m,s,t] / E[m,s,t0], 0) / (GDP[c,s,t] / GDP[c,s,t0])
margin[i,s,t] = margin0[i] - (1 - pi) * (P[s,t] - P[s,t0]) * e[i,s,t]
V/D[i,s,t]    = V/D[i,t0] * (margin[i,s,t] / margin0[i]) / (1 + abatement debt share)
DD            = (ln(V/D) - sigma^2 / 2) / sigma                     (Merton, T = 1, drift 0)
PD            = Phi(-(DD + c[country, section]));  PD = 1 if margin <= 0
EL            = PD * 40% * exposure
```

- **Carbon cost channel.** The IAM carbon price above its 2025 level multiplies the firm's Scope 1 intensity. It is applied as a flat tax on direct emissions, as in OP 281. The pass-through share pi is 0 by default.
- **Abatement.** A firm's intensity follows the IAM emissions of its sector, relative to 2025, divided by GDP growth. Net IAM emissions turn negative in some sectors because of carbon capture and removals. The ratio is floored at zero, so a firm never earns carbon revenue.
- **GDP channel.** Revenue grows with NiGEM real GDP. With a constant capital structure (OP 281, Appendix B, step 5), revenue growth moves value and debt together. In this specification GDP therefore acts only through emission intensity. This is a property of the design, and it is stated here because it explains why Current Policies shows a flat PD.
- **Debt-financed abatement investment.** OP 281 calibrates the replacement cost per tonne on IMF (2019) but does not report the value. The cited article reports costs by technology, not a single figure ([IMF F&D, December 2019](https://www.imf.org/en/publications/fandd/issues/2019/12/the-true-cost-of-reducing-greenhouse-gas-emissions-gillingham)). The channel is implemented and tested but set to 0. No untraceable number enters the results.

### 2.2 Calibration

The constant c is solved with Brent's method, per country and NACE section. It sets the exposure-weighted PD in 2025 equal to an anchor: the obligor-weighted average historical annual default rate of general corporates in Pillar 3 template EU CR9, for the two largest IRB banks in each country at 31 December 2025. The default range is excluded.

| Country | Banks | Obligors | Anchor PD |
|---|---|---|---|
| IT | Intesa Sanpaolo (A-IRB, F-IRB), UniCredit (A-IRB, F-IRB) | 226,059 | 1.69% |
| DE | Deutsche Bank (A-IRB, F-IRB), DZ BANK (F-IRB) | 136,624 | 0.39% |

The regulatory default definition (Article 178 CRR) is identical in both countries. The German anchor comes mostly from Deutsche Bank. Its "historical" column equals the 2025 observed rate because the five-year average is being phased in for the new CRR3 exposure classes (Deutsche Bank Pillar 3 2025, p. 139). A single year in a low-default period can understate the through-the-cycle rate. A cross-check points the same way: Destatis reports 69 insolvencies per 10,000 enterprises in Germany in 2025 ([Destatis, March 2026](https://www.destatis.de/DE/Presse/Pressemitteilungen/2026/03/PD26_085_52411.html)), i.e. 0.69%, above the 0.39% anchor, although the populations differ (all legal units, including sole proprietors, against IRB-rated corporates). Every row, with bank, page and URL, is in `data/ref/cr9_rows.csv`.

### 2.3 Portfolio

**Firm-level mode (reference).** The portfolio is simulated from BACH, the harmonised company-accounts database of the European Committee of Central Balance-Sheet Data Offices (release of 14 September 2026, year 2023, variable sample). For each NACE division and size class (small, medium, large) with complete quartiles, 200 firms are drawn: 320 cells and 64,000 firms for Italy and Germany together.

- **Margin:** BACH ratio R32, gross operating profit over net turnover, drawn from a piecewise-linear quantile function through Q1, median and Q3. Firms below a 0.5% margin are excluded, consistent with the rule that EBITDA must be positive at t0. On average 8.6% of firms per cell fall below.
- **Leverage:** net debt over gross operating profit, the inverse of BACH ratio R27. Its quartiles map one to one from R27 when R27 Q1 is positive; cells where it is not are excluded. Net debt at or below zero (6.7% of draws) means no default barrier and PD 0. Net debt is capped at 20 times gross operating profit (11.8% of draws). Near-zero profits otherwise produce unbounded leverage, and the calibration then puts all default risk in that tail. The ECB guidance on leveraged transactions (2017) already treats debt above 6 times EBITDA as highly leveraged, so the cap only trims the extreme tail. Caps of 10x and 40x are shown as sensitivities.
- **Asset value:** EV/EBITDA times gross operating profit, with the multiple and the firm-value volatility from Damodaran Europe (January 2026, positive-EBITDA firms), mapped by industry (`data/ref/sector_map.csv`).
- **Scope 1 intensity:** the A64 industry intensity from Eurostat air emissions accounts (`env_ac_ainah_r2`, GHG) over output (`nama_10_a64`, P1), 2023. It is the same for every firm in an industry.
- **Exposure:** gross loans to non-financial corporations by NACE section from Pillar 3 template EU CQ5 at 31 December 2025, Intesa Sanpaolo for IT (€161.1 billion in scope) and Deutsche Bank for DE (€157.6 billion). Each section is split across cells by amounts owed to credit institutions (BACH item L2), then equally across the firms of a cell.

Sections with no usable BACH cell keep one representative firm per A64 industry: DE A, B, E, I and IT P, Q.

**Representative-firm mode (sensitivity).** One firm per A64 industry, margin = gross operating surplus over output from Eurostat (B1G - D1 - D29X39 over P1), exposure split by value added. In this mode leverage cancels: the calibration constant absorbs it, and an EBITDA shock moves DD by ln(margin_t / margin_0) / sigma.

### 2.4 Scenarios

The scenarios are NGFS Phase V, retrieved from the IIASA Scenario Explorer (`ngfs_phase_5`, guest access). The reference IAM is GCAM 6.0, chosen because EU-15 is the finest native region that contains both Italy and Germany. MESSAGEix-GLOBIOM and REMIND-MAgPIE are sensitivities.

- **Sector emissions:** downscaled country series where available (industry energy plus industrial processes, transport, residential and commercial). The IAM region is used for electricity, energy supply and AFOLU methane.
- **GDP:** the NiGEM Baseline level times the transition-only deviation, with chronic physical damages excluded. Current Policies is not reported in the transition variant and is set equal to Baseline. Low demand has no NiGEM transition GDP and is skipped.
- **Currency:** carbon prices are converted from US$2010 to EUR at 2023 prices with the ECB 2010 average rate (1.3257 USD per EUR) and the euro area GDP deflator (94.258 in 2010, 122.348 in 2023): 1 US$2010 = €0.979.

| Carbon price, €/t (2023 prices) | 2030 | 2040 | 2050 |
|---|---|---|---|
| GCAM, Net Zero 2050 | 79 | 373 | 1,548 |
| GCAM, Delayed transition | 0 | 185 | 910 |
| MESSAGEix, Net Zero 2050 | 242 | 320 | 472 |
| REMIND, Net Zero 2050 | 278 | 696 | 1,020 |

The NGFS licence allows research and commercial use but restricts redistribution of substantial parts of the data ([Zenodo record](https://zenodo.org/records/15790097)). The repository therefore ships the download script, not the data.

## 3. Results (GCAM, pass-through 0, firm-level portfolio)

**Portfolio PD, change versus Current Policies (percentage points)**

| | 2030 | 2040 | 2050 | Peak |
|---|---|---|---|---|
| IT, Net Zero 2050 | +2.66 | +4.72 | +2.77 | +4.96 (2042) |
| IT, Delayed transition | 0.00 | +3.87 | +2.81 | +4.18 (2042) |
| DE, Net Zero 2050 | +0.40 | +1.23 | +0.32 | +1.38 (2042) |
| DE, Delayed transition | 0.00 | +0.58 | +0.23 | +0.78 (2043) |

1. **The shock is hump-shaped in time.** Carbon prices rise faster than emission intensities fall until the early 2040s. After that, sector decarbonisation removes the base the price applies to, so the PD increase peaks in 2042 under Net Zero 2050. A Delayed transition starts in 2030 and peaks at a similar time.
2. **Dispersion matters most in the near term.** With firm-level margins and leverage, the Italian 2030 shift under Net Zero is +2.66 pp, against +0.53 pp with one representative firm per industry. Thin-margin firms cross the default threshold first; the Merton PD is convex, so averaging firms hides them. By 2050 the two modes converge (+2.77 pp against +2.40 pp).
3. **Risk concentrates in few sectors.** In 2040, under Net Zero 2050, the largest section shifts are:
   - agriculture: IT +96.5 pp, DE +88.4 pp;
   - Italian water and waste: +26.6 pp;
   - transport: IT +18.9 pp, DE +7.6 pp;
   - manufacturing: IT +2.3 pp, DE +4.2 pp.

   Most service sections move by less than 0.7 pp.
4. **The Italian 2050 figure depends on one assumption.** Agriculture is 2% of Italian exposure, but its CH4 and N2O emissions, priced at the full economy-wide carbon price with no pass-through, wipe out farm margins. With agriculture exempt from the carbon price, the Italian 2050 shift falls from +2.77 pp to +0.63 pp, and the German one from +0.32 pp to +0.16 pp. The NGFS carbon price is a proxy for economy-wide policy intensity. EU agriculture is currently outside the ETS. Both readings are shown, and the reader should not take the headline number without this sensitivity.
5. **The Italy-Germany gap has two sources.** The anchors differ (1.69% against 0.39%). The sector mix also differs: Deutsche Bank's CQ5 book is weighted towards real estate and other services, which carry low emissions.

**Sensitivity, Net Zero 2050 versus Current Policies, portfolio PD change in 2050 (pp)**

| Variant | IT | DE |
|---|---|---|
| Reference | 2.77 | 0.32 |
| Pass-through 50% | 2.47 | 0.18 |
| Volatility x0.8 / x1.2 | 2.81 / 2.73 | 0.33 / 0.31 |
| Agriculture unpriced | 0.63 | 0.16 |
| MESSAGEix-GLOBIOM | 3.62 | 0.52 |
| REMIND-MAgPIE | 2.97 | 0.49 |
| Leverage cap 10x / 40x | 2.91 / 2.66 | 0.37 / 0.32 |
| Representative firm | 2.40 | 0.42 |

The pricing of agricultural emissions changes the Italian 2050 result by 2.1 pp, and model choice by up to 0.9 pp. The leverage cap, volatility and portfolio mode move it by less than 0.4 pp.

## 4. Limitations

1. **Independent draws.** Margin and leverage are drawn independently within a cell, so their correlation is lost. Emission intensity is the industry average for every firm in that industry.
2. **PD jumps to 100%.** Where EBITDA reaches zero the PD becomes 1. This happened in 104,095 of the 9,985,560 projection cells (1.0%) of the reference run, agriculture 35%, transport 31%, manufacturing 17%, water and waste 15%. The rule is conservative and produces jumps.
3. **Borrowed valuation inputs.** Asset volatilities and multiples come from listed European peers and are applied to SMEs. The 20x leverage cap is a modelling choice; the 10x and 40x sensitivities bound its effect.
4. **Uniform anchor within a country.** Sector differences in the starting PD come from the BACH leverage distribution and from volatility, not from observed sector default rates. Full sector series need registered access (Destatis GENESIS); the public Destatis release covers four of seventeen sections.
5. **Fixed balance sheet and base year.** Exposures are static, 2023 financials are taken as 2025 values, and one bank's CQ5 book stands in for each country.
6. **Omitted channels.** The energy-cost channel via Scope 2, the Scope 3 revenue channel and physical risk from OP 281 are not in v1. The abatement-investment channel is implemented but switched off, because its calibration value is not traceable.
7. **Public inputs only.** The engine uses only public data and public methodology. BACH requires free registration.

## 5. Reproduction

```
python scripts/download.py        # BACH: download bach.zip after free registration, unzip into data/raw/
python run.py config.toml
python -m pytest tests
```

Outputs are written to `results/`: sector and portfolio PD paths, expected loss, sensitivities, rejected loans, three charts and `manifest.json` (input hashes, anchors, counts).
