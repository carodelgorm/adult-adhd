#!/usr/bin/env python3
"""
Percent increase in Medicare Part D stimulant prescribing for beneficiaries 65+.

Source:
  CMS "Medicare Part D Prescribers - by Geography and Drug", National rows.
  This file breaks each drug out into all-ages totals and a 65+ subset
  (GE65_* fields), so unlike the Part D Spending by Drug file used by
  build_medicare_partd_stimulant_2019_2024.py it can isolate seniors.

Limitations:
  1) CMS publishes only a single age cut (65+). No public CMS file splits
     drug-level prescribing into 65-70 vs 71+; that requires beneficiary-level
     Part D event data (ResDAC research identifiable files).
  2) Beneficiary counts are unique within a drug row. Summing across
     stimulant products double-counts people who used more than one product,
     so the class total is labeled Bene_Product_Counts. Claims and 30-day
     fills are additive and are the preferred volume measures.
  3) Raw counts, not rates: growth partly reflects growth in the number of
     Medicare Part D enrollees aged 65+.
  4) GE65 values are suppressed for drug rows with fewer than 11 claims or
     beneficiaries; at the national level this affects only rare products,
     and the script reports how many rows were suppressed.

Usage:
  python stimulant_growth_65plus.py
  python stimulant_growth_65plus.py --start 2013 --end 2024 --out growth.xlsx
"""

from __future__ import annotations
import argparse
import re
from pathlib import Path
import pandas as pd
import requests

# Dataset UUIDs from https://data.cms.gov/data.json
# ("Medicare Part D Prescribers - by Geography and Drug", one per data year).
DATASETS = {
    2013: "9aec2a70-4ef2-438a-bc35-1747fe2492c9",
    2014: "63099eb4-6c9e-4fec-8c9e-b6b132f1b7f4",
    2015: "73748d0b-2acb-420a-ac66-27d8e238fdc8",
    2016: "c5b3c840-5eb2-4e4c-ac35-c30995dcb051",
    2017: "7863e41c-3f6f-4889-93a8-be65e9f3d073",
    2018: "b083c9b6-b841-4676-8d0a-fb03ee1431a1",
    2019: "73a6335e-f16f-4c81-a84b-6b5a986e2bf8",
    2020: "83891e77-99cf-4865-b60a-97703b916e09",
    2021: "7dda2a9d-034a-446a-b4b3-e1254e0127b2",
    2022: "1fc57194-a51d-4864-aee6-de0889488151",
    2023: "3463648b-1971-478d-84ca-80cadc758153",
    2024: "c8ea3f8e-3a09-4fea-86f2-8902fb4b0920",
}
API = "https://data.cms.gov/data-api/v1/dataset/{uuid}/data"
PAGE_SIZE = 5000

# Same Schedule II ADHD-stimulant scope as the spending build script.
STIMULANT_RE = re.compile(
    r"amphetamine|dextroamphetamine|lisdexamfetamine|"
    r"methylphenidate|dexmethylphenidate|serdexmethylphenidate|"
    r"methamphetamine",
    flags=re.I,
)

NUMERIC = [
    "Tot_Clms", "Tot_30day_Fills", "Tot_Drug_Cst", "Tot_Benes",
    "GE65_Tot_Clms", "GE65_Tot_30day_Fills", "GE65_Tot_Drug_Cst", "GE65_Tot_Benes",
]


def fetch_national(year: int) -> pd.DataFrame:
    url = API.format(uuid=DATASETS[year])
    rows, offset = [], 0
    while True:
        params = {"filter[Prscrbr_Geo_Lvl]": "National", "size": PAGE_SIZE, "offset": offset}
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        page = r.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    df = pd.DataFrame(rows)
    df["Year"] = year
    return df


def stimulant_rows(df: pd.DataFrame) -> pd.DataFrame:
    text = df["Gnrc_Name"].fillna("") + " | " + df["Brnd_Name"].fillna("")
    out = df[text.str.contains(STIMULANT_RE, na=False)].copy()
    for c in NUMERIC:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["GE65_Suppressed"] = (
        out["GE65_Sprsn_Flag"].fillna("").str.strip().ne("")
        | out["GE65_Bene_Sprsn_Flag"].fillna("").str.strip().ne("")
    )
    return out


def annual_summary(detail: pd.DataFrame) -> pd.DataFrame:
    g = detail.groupby("Year")
    s = pd.DataFrame({
        "GE65_Claims": g["GE65_Tot_Clms"].sum(),
        "GE65_30day_Fills": g["GE65_Tot_30day_Fills"].sum(),
        "GE65_Bene_Product_Counts": g["GE65_Tot_Benes"].sum(),
        "GE65_Drug_Cost": g["GE65_Tot_Drug_Cst"].sum(),
        "All_Ages_Claims": g["Tot_Clms"].sum(),
        "All_Ages_30day_Fills": g["Tot_30day_Fills"].sum(),
        "Product_Rows": g.size(),
        "GE65_Suppressed_Rows": g["GE65_Suppressed"].sum(),
    })
    s["Under65_Claims"] = s["All_Ages_Claims"] - s["GE65_Claims"]
    s["GE65_Share_of_Claims"] = s["GE65_Claims"] / s["All_Ages_Claims"]
    return s.reset_index()


def growth_table(annual: pd.DataFrame) -> pd.DataFrame:
    first, last = annual.iloc[0], annual.iloc[-1]
    n = int(last["Year"] - first["Year"])
    metrics = [
        "GE65_Claims", "GE65_30day_Fills", "GE65_Bene_Product_Counts",
        "GE65_Drug_Cost", "Under65_Claims", "All_Ages_Claims",
    ]
    rows = []
    for m in metrics:
        a, b = first[m], last[m]
        rows.append({
            "Metric": m,
            f"{int(first['Year'])}": a,
            f"{int(last['Year'])}": b,
            "Percent_Change": b / a - 1,
            "CAGR": (b / a) ** (1 / n) - 1 if n else float("nan"),
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, default=2019)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--out", default="stimulant_growth_65plus.xlsx")
    args = ap.parse_args()

    frames = []
    for year in range(args.start, args.end + 1):
        print(f"Fetching {year} ...")
        frames.append(stimulant_rows(fetch_national(year)))
    detail = pd.concat(frames, ignore_index=True)

    annual = annual_summary(detail)
    for c in ["GE65_Claims", "GE65_30day_Fills", "GE65_Bene_Product_Counts", "GE65_Drug_Cost"]:
        annual[f"YoY_{c}"] = annual[c].pct_change()
    growth = growth_table(annual)

    keep = ["Year", "Brnd_Name", "Gnrc_Name"] + NUMERIC + ["GE65_Sprsn_Flag", "GE65_Bene_Sprsn_Flag"]
    with pd.ExcelWriter(Path(args.out), engine="xlsxwriter") as writer:
        growth.to_excel(writer, sheet_name="Growth", index=False)
        annual.to_excel(writer, sheet_name="Annual_65plus", index=False)
        detail[keep].to_excel(writer, sheet_name="Product_Detail", index=False)

    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(f"\nWrote {Path(args.out).resolve()}\n")
    print(annual[["Year", "GE65_Claims", "GE65_30day_Fills", "GE65_Bene_Product_Counts",
                  "GE65_Drug_Cost", "Under65_Claims", "GE65_Share_of_Claims",
                  "Product_Rows", "GE65_Suppressed_Rows"]].to_string(index=False))
    print()
    print(growth.to_string(index=False))


if __name__ == "__main__":
    main()
