"""Germany: insolvency frequency by WZ 2008 section, from the Destatis GENESIS API (needs GENESIS_TOKEN in .env.local).

Rate = insolvent enterprises in year t per legal unit in the business register of year t-1 (the register for the
latest year is not yet published). Written to data/ref/de_insolvency_rates.csv. Used only for sector relatives.
"""
import io
import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://genesis.destatis.de/genesisWS/rest/2020"


def token():
    for line in (ROOT / ".env.local").read_text().splitlines():
        if line.startswith("GENESIS_TOKEN="):
            return line.split("=", 1)[1].strip()
    return os.environ["GENESIS_TOKEN"]


def table(name, tok):
    data = urllib.parse.urlencode({"name": name, "area": "all", "format": "ffcsv", "startyear": 2019,
                                   "endyear": 2025, "language": "de"}).encode()
    req = urllib.request.Request(f"{BASE}/data/tablefile", data=data, headers={"username": tok, "password": ""})
    with urllib.request.urlopen(req, timeout=300) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    return z.read(z.namelist()[0]).decode("utf-8-sig")


def main():
    tok = token()
    raw = ROOT / "data" / "raw"
    for t in ("52411-0068", "52111-0002"):
        (raw / f"destatis_{t}.csv").write_text(table(t, tok))
    c = duckdb.connect()
    c.sql(f"""create view ins as select time::int y, "3_variable_attribute_code" sec, "3_variable_attribute_label" lab,
        sum(try_cast(value as double)) v from read_csv('{raw}/destatis_52411-0068.csv', delim=';', all_varchar=true)
        where "3_variable_attribute_code" like 'WZ08-%' group by 1,2,3""")
    c.sql(f"""create view ent as select time::int y, "3_variable_attribute_code" sec, try_cast(value as double) n
        from read_csv('{raw}/destatis_52111-0002.csv', delim=';', all_varchar=true)
        where "3_variable_attribute_code" like 'WZ08-%' and "2_variable_attribute_code" is null""")
    c.sql(f"""copy (select replace(ins.sec, 'WZ08-', '') as section, ins.lab as section_name, ins.y as year,
        ins.v as insolvencies, ent.n as legal_units, 10000 * ins.v / ent.n as per_10000,
        'Destatis GENESIS 52411-0068 / 52111-0002' as source
        from ins join ent on ins.sec = ent.sec and ent.y = ins.y - 1 order by 1, 3)
        to '{ROOT / "data" / "ref" / "de_insolvency_rates.csv"}' (header, delimiter ',')""")


if __name__ == "__main__":
    main()
