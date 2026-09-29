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

The regulatory default definition (Article 178 CRR) is identical in both countries. The German anchor comes mostly from Deutsche Bank. Its "historical" column equals the 2025 observed rate because the five-year average is being phased in for the new CRR3 exposure classes (Deutsche Bank Pillar 3 2025, p. 139). A single year in a low-default period can understate the through-the-cycle rate. Every row, with bank, page and URL, is in `data/ref/cr9_rows.csv`.

### 2.3 Portfolio (representative-firm mode)

v1 uses one representative firm per country and A64 industry (58 industries, NACE sections A-S excluding K and O). All inputs are for 2023:

- **Scope 1 intensity:** Eurostat air emissions accounts (`env_ac_ainah_r2`, GHG, thousand tonnes CO2e) divided by output (`nama_10_a64`, P1).
- **Margin:** gross operating surplus over output, derived as B1G - D1 - D29X39 over P1 (`nama_10_a64`). Intensity and margin share the same denominator, so carbon cost over EBITDA equals price times emissions over operating surplus.
- **Multiple and volatility:** Damodaran Europe, January 2026, "EV/EBITDA" of positive-EBITDA firms and standard deviation of firm value, mapped by industry (`data/ref/sector_map.csv`).
- **Exposure:** gross loans to non-financial corporations by NACE section from Pillar 3 template EU CQ5 at 31 December 2025, Intesa Sanpaolo for IT (€161.1 billion in scope) and Deutsche Bank for DE (€157.6 billion). Each section is split across A64 industries by value-added share.

In this mode the leverage level cancels out: the calibration constant absorbs it, and a relative EBITDA shock moves DD by ln(margin_t / margin_0) / sigma, whatever the leverage. Firm-level dispersion from BACH (quartiles of gross operating profit over net debt, ratio R27) is the planned second mode. BACH requires a registered login.

One loan is rejected: Italian postal services (H53) has negative gross operating surplus in 2023 (EBITDA -€211 million on €9.1 billion of output), so the Merton value is undefined.

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

## 3. Results (GCAM, pass-through 0)

**Portfolio PD, change versus Current Policies (percentage points)**

| | 2030 | 2040 | 2050 | Peak |
|---|---|---|---|---|
| IT, Net Zero 2050 | +0.53 | +3.18 | +2.40 | +4.06 (2043) |
| IT, Delayed transition | 0.00 | +1.49 | +2.43 | +2.72 (2047) |
| DE, Net Zero 2050 | +0.09 | +1.01 | +0.42 | +1.22 (2042) |
| DE, Delayed transition | 0.00 | +0.33 | +0.33 | +0.57 (2046) |

1. **The shock is hump-shaped in time.** Carbon prices rise faster than emission intensities fall until the early 2040s. After that, sector decarbonisation removes the base the price applies to, so the PD increase peaks in 2042-2043 under Net Zero 2050. A Delayed transition shifts the peak to 2046-2047 and keeps it high at 2050.
2. **Risk concentrates in few sectors.** In 2040, under Net Zero 2050, the largest section shifts are agriculture (IT +58.9 pp, DE +88.4 pp), Italian water and waste (+45.2 pp), transport (IT +11.4 pp, DE +13.7 pp) and manufacturing (+1.7 pp in both). Most service sections move by less than 0.1 pp.
3. **The Italian portfolio result depends on one assumption.** Agriculture is 2% of Italian exposure, but its CH4 and N2O emissions, priced at the full economy-wide carbon price with no pass-through, wipe out its EBITDA. With agriculture exempt from the carbon price, the Italian 2050 shift falls from +2.40 pp to +0.37 pp, and the German one from +0.42 pp to +0.26 pp. The NGFS carbon price is a proxy for economy-wide policy intensity. EU agriculture is currently outside the ETS. Both readings are shown, and the reader should not take the headline number without this sensitivity.
4. **The Italy-Germany gap has two sources.** The anchors differ (1.69% against 0.39%). The sector mix also differs: Deutsche Bank's CQ5 book is weighted towards real estate and other services, which carry low emissions.

**Sensitivity, Net Zero 2050 versus Current Policies, portfolio PD change in 2050 (pp)**

| Variant | IT | DE |
|---|---|---|
| Reference | 2.40 | 0.42 |
| Pass-through 50% | 2.18 | 0.21 |
| Volatility x0.8 / x1.2 | 2.50 / 2.32 | 0.50 / 0.35 |
| Agriculture unpriced | 0.37 | 0.26 |
| MESSAGEix-GLOBIOM | 1.95 | 0.35 |
| REMIND-MAgPIE | 2.66 | 0.22 |

Model choice changes the 2050 result by up to 0.7 pp in Italy. The pricing of agricultural emissions changes it by 2.0 pp. Volatility matters least.

## 4. Limitations

1. **One firm per industry.** The representative-firm mode ignores dispersion within industries. Because the Merton PD is convex, this understates the tail; BACH quartiles address it.
2. **PD jumps to 100%.** Where EBITDA reaches zero the PD becomes 1. This happened in 91 of the 17,940 projection cells of the reference run (115 loans, 6 scenarios, 26 years), concentrated in air and sea transport and agriculture. The rule is conservative and produces jumps.
3. **Borrowed volatilities and multiples.** Asset volatilities and multiples come from listed European peers and are applied to whole industries.
4. **Uniform anchor within a country.** Sector differences in the starting PD come only from volatility. Sector relatives (Banca d'Italia deterioration rates by ATECO, Destatis insolvency frequency by WZ 2008) are planned.
5. **Fixed balance sheet and base year.** Exposures are static, 2023 financials are taken as 2025 values, and one bank's CQ5 book stands in for each country.
6. **Omitted channels.** The energy-cost channel via Scope 2, the Scope 3 revenue channel and physical risk from OP 281 are not in v1. The abatement-investment channel is implemented but switched off, because its calibration value is not traceable.
7. **Public inputs only.** The engine uses only public data and public methodology.

## 5. Reproduction

```
python scripts/download.py
python run.py config.toml
python -m pytest tests
```

Outputs are written to `results/`: sector and portfolio PD paths, expected loss, sensitivities, rejected loans, three charts and `manifest.json` (input hashes, anchors, counts).
