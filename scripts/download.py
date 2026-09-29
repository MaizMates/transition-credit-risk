"""Download all public inputs into data/raw/. NGFS data must not be redistributed (licence), so data/raw is not versioned."""
import csv
import urllib.request
from pathlib import Path

import pyam
import xlrd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0"}

IAMS = {  # model -> native region containing IT and DE
    "GCAM 6.0 NGFS": "GCAM 6.0 NGFS|EU-15",
    "MESSAGEix-GLOBIOM 2.0-M-R12-NGFS": "MESSAGEix-GLOBIOM 2.0-R12|Western Europe",
    "REMIND-MAgPIE 3.3-4.8": "REMIND-MAgPIE 3.3-4.8|EU 28",
}
IAM_VARS = [
    "Price|Carbon",
    "Emissions|CO2|Energy|Demand|Industry",
    "Emissions|CO2|Industrial Processes",
    "Emissions|CO2|Energy|Demand|Transportation",
    "Emissions|CO2|Energy|Demand|Residential and Commercial",
    "Emissions|CO2|Energy|Supply|Electricity",
    "Emissions|CO2|Energy|Supply",
    "Emissions|CH4|AFOLU",
]
GDP_VARS = ["Gross Domestic Product (GDP)", "Gross Domestic Product (GDP)(transition)"]


def get(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        path.write_bytes(r.read())


def ngfs():
    frames = []
    for model, region in IAMS.items():
        frames.append(pyam.read_iiasa("ngfs_phase_5", model=model, region=region, variable=IAM_VARS, meta=False))
        frames.append(pyam.read_iiasa("ngfs_phase_5", model=f"Downscaling[{model}]", region=["ITA", "DEU"],
                                      variable=IAM_VARS, meta=False))
        nigem = f"NiGEM NGFS v1.24.2[{model}]"
        frames.append(pyam.read_iiasa("ngfs_phase_5", model=nigem, variable=GDP_VARS, meta=False,
                                      region=["NiGEM NGFS v1.24.2|Italy", "NiGEM NGFS v1.24.2|Germany"]))
    pyam.concat(frames).data.to_csv(RAW / "ngfs_phase5.csv", index=False)


def eurostat():
    base = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
    get(f"{base}/env_ac_ainah_r2/A.GHG..THS_T.IT+DE?format=SDMX-CSV&startPeriod=2023&endPeriod=2023",
        RAW / "eurostat_air_emissions.csv")
    get(f"{base}/nama_10_a64/A.CP_MEUR..P1+B1G+D1+D29X39.IT+DE?format=SDMX-CSV&startPeriod=2023&endPeriod=2023",
        RAW / "eurostat_nama_a64.csv")


def damodaran():
    for name in ["vebitdaEurope", "optvarEurope"]:
        xls = RAW / f"{name}.xls"
        get(f"https://pages.stern.nyu.edu/~adamodar/pc/datasets/{name}.xls", xls)
        sh = xlrd.open_workbook(xls).sheet_by_name("Industry Averages")
        rows = [[c.value for c in sh.row(r)] for r in range(sh.nrows)]
        head = next(i for i, r in enumerate(rows) if r[0] == "Industry Name")
        with open(RAW / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(rows[head])
            w.writerows(r for r in rows[head + 1:] if r[0] and r[0] != "Total Market")


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    eurostat()
    damodaran()
    ngfs()
    print("done")
