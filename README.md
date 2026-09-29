# Transition credit risk engine

Translates NGFS Phase V transition scenarios into probabilities of default and expected loss for a
non-financial corporate loan book, by NACE sector, for Italy and Germany, 2025-2050. Merton PD,
calibrated on Pillar 3 default rates; transmission channels from the ECB economy-wide climate
stress test (Occasional Paper 281). Public data only.

Method, sources, results and limitations: [docs/technical-note.md](docs/technical-note.md).

![PD shift by sector](results/chart_pd_shift_by_sector.png)

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install duckdb numpy scipy matplotlib pytest pyam-iamc "sqlalchemy<2.1" xlrd
.venv/bin/python scripts/download.py     # NGFS (IIASA), Eurostat, Damodaran into data/raw/
.venv/bin/python run.py config.toml      # results/
.venv/bin/python -m pytest tests
```

`data/raw/` is not versioned: the NGFS licence restricts redistribution of the scenario data.

## Layout

| Path | Content |
|---|---|
| `config.toml` | Every parameter, with its source |
| `data/ref/cr9_rows.csv` | Pillar 3 EU CR9 rows used for the PD anchors (bank, page, URL) |
| `data/ref/cq5_weights.csv` | Pillar 3 EU CQ5 loans by NACE section, used as exposure weights |
| `data/ref/sector_map.csv` | A64 industry to NACE section, NGFS emission sector, Damodaran industry |
| `tcr/scenarios.py` | NGFS paths: carbon price, sector emissions, GDP; annual interpolation |
| `tcr/portfolio.py` | Loan tape validation; representative-firm portfolio |
| `tcr/engine.py` | Carbon-cost projection, Merton PD, calibration |
| `tcr/report.py` | CSV outputs and charts |
| `results/` | `pd_portfolio.csv`, `pd_by_sector.csv`, `sensitivity.csv`, `rejected.csv`, `manifest.json`, charts |

## Own loan tape

`tcr.portfolio.validate` applies the schema in the design spec (loan_id, firm_id, country, nace,
size_class, revenue, ebitda, financial_debt, exposure, ghg_t). Rows that fail a rule go to
`results/rejected.csv` with the rule; none are dropped silently.
