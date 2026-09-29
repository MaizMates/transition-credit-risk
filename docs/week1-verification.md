# Week-1 verification log (spec section 7.2)

Date: 2026-09-29. Decisions taken autonomously on Marco's instruction; to be reviewed at the end.

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
