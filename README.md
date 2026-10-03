# Transition credit risk engine: NGFS scenarios to corporate PDs

![tests](https://github.com/MaizMates/transition-credit-risk/actions/workflows/tests.yml/badge.svg)

An open, reproducible engine that translates **NGFS Phase V transition scenarios** into
**probabilities of default and expected loss** for a non-financial corporate loan book, by NACE
sector, for **Italy and Germany, 2025-2050**.

- **Transmission channels** follow the ECB economy-wide climate stress test (Occasional Paper 281): carbon cost on Scope 1 emissions, sector abatement, GDP.
- **PDs** come from a **Merton** structural model, calibrated on default rates disclosed in banks' **Pillar 3 (EU CR9)**.
- **Public data only:** NGFS/IIASA, Eurostat, BACH (free registration), Damodaran, Pillar 3 reports. Every number is traceable to a source, a page or a file hash.

Context: EBA/GL/2025/04 on environmental scenario analysis apply from 1 January 2027 and require
banks to integrate environmental risks into stress testing and resilience analysis.

**Full method, sources and limitations: [docs/technical-note.md](docs/technical-note.md).**

## Key results (Net Zero 2050 vs Current Policies, GCAM, no cost pass-through)

Firm-level portfolio: 64,000 firms simulated from BACH company-accounts quartiles, weighted by the
sector mix of the two largest banks' Pillar 3 books.

| Portfolio PD change | 2030 | 2040 | 2050 | Peak |
|---|---|---|---|---|
| Italy | +2.66 pp | +4.72 pp | +2.77 pp | +4.96 pp (2042) |
| Germany | +0.40 pp | +1.23 pp | +0.32 pp | +1.38 pp (2042) |

1. **Hump-shaped risk.** The PD increase peaks in 2042. Carbon prices rise faster than sector emissions fall until then; afterwards decarbonisation shrinks the base the price applies to.
2. **Dispersion matters.** Thin-margin firms cross the default threshold first. With firm-level data the Italian 2030 shift is +2.66 pp, against +0.53 pp with one representative firm per industry.
3. **Concentrated risk.** In 2040 the largest shifts are in agriculture, Italian waste management (+27 pp) and transport (IT +19 pp, DE +8 pp); manufacturing moves +2 to +4 pp.
4. **One assumption drives the Italian 2050 figure.** If agricultural CH4/N2O is exempt from the carbon price, the Italian 2050 shift falls from +2.77 pp to +0.63 pp. Scenario-model choice moves it by up to 0.9 pp; the leverage cap and volatility by less than 0.2 pp.

![PD shift by sector](results/chart_pd_shift_by_sector.png)
![Portfolio PD path](results/chart_portfolio_pd_path.png)
![Sensitivities](results/chart_sensitivity.png)

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/download.py     # NGFS (IIASA), Eurostat, Damodaran into data/raw/
# BACH: register (free) at bach.banque-france.fr, Data selection > Download the complete database, unzip into data/raw/
.venv/bin/python run.py config.toml      # writes results/
.venv/bin/python -m pytest tests         # 11 tests: Merton, calibration, channels, interpolation, validation, BACH sampling
```

`data/raw/` is not versioned: the NGFS licence restricts redistribution of the scenario data.

## Layout

| Path | Content |
|---|---|
| `config.toml` | Every parameter, with its source |
| `data/ref/cr9_rows.csv` | Pillar 3 EU CR9 rows behind the PD anchors (bank, page, URL) |
| `data/ref/cq5_weights.csv` | Pillar 3 EU CQ5 loans by NACE section, used as exposure weights |
| `data/ref/sector_map.csv` | A64 industry to NACE section, NGFS emission sector, Damodaran industry |
| `tcr/scenarios.py` | NGFS paths: carbon price, sector emissions, GDP; annual interpolation |
| `tcr/portfolio.py` | Loan-tape validation; firm-level portfolio from BACH quartiles; representative-firm fallback |
| `tcr/engine.py` | Carbon-cost projection, Merton PD, calibration |
| `tcr/report.py` | CSV outputs and charts |
| `results/` | PD paths by sector and portfolio, expected loss, sensitivities, rejected loans, manifest with input hashes |
| `docs/` | Technical note, original design spec, decision log |

## Using your own loan tape

`tcr.portfolio.validate` applies the input schema (loan_id, firm_id, country, nace, size_class,
revenue, ebitda, financial_debt, exposure, ghg_t). Rows that fail a rule go to
`results/rejected.csv` with the rule; none are dropped silently.

## Author

Marco Izzo. MIT licence for the code. Scenario data © NGFS/IIASA, used under its licence and not redistributed.
