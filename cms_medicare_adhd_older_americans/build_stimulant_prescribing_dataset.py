#!/usr/bin/env python3
"""
Build an analysis-ready file of Medicare Part D stimulant prescribing, 2013-2024.

Source:
  CMS "Medicare Part D Prescribers - by Geography and Drug" (one release per
  data year). Every stimulant brand/generic row is kept at both the National
  and State prescriber-geography levels, with the all-ages and 65+ (GE65_*)
  fields CMS publishes, plus derived under-65 fields and an ingredient family.

Output (one row per Year x geography x brand/generic product):
  data/medicare_partd_stimulant_prescribing_2013_2024.csv
  See data/README.md for the data dictionary and caveats.

Usage:
  python build_stimulant_prescribing_dataset.py
  python build_stimulant_prescribing_dataset.py --start 2019 --end 2024 --out my.csv
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import requests

from build_medicare_partd_stimulant_2019_2024 import STIMULANT_RE, ingredient_family

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

# Case-insensitive substrings passed to the CMS API to narrow the download;
# STIMULANT_RE is then applied locally as the authoritative scope.
#   "amphetamine" -> amphetamine, dextroamphetamine, methamphetamine
#   "amfetamine"  -> lisdexamfetamine
#   "phenidate"   -> methylphenidate, dexmethylphenidate, serdexmethylphenidate
API_TERMS = ["amphetamine", "amfetamine", "phenidate"]

NUMERIC = [
    "Tot_Prscrbrs", "Tot_Clms", "Tot_30day_Fills", "Tot_Drug_Cst", "Tot_Benes",
    "GE65_Tot_Clms", "GE65_Tot_30day_Fills", "GE65_Tot_Drug_Cst", "GE65_Tot_Benes",
    "LIS_Bene_Cst_Shr", "NonLIS_Bene_Cst_Shr",
]


def fetch_term(year: int, term: str) -> list[dict]:
    url = API.format(uuid=DATASETS[year])
    rows, offset = [], 0
    while True:
        params = {
            "filter[g][condition][path]": "Gnrc_Name",
            "filter[g][condition][operator]": "CONTAINS",
            "filter[g][condition][value]": term,
            "size": PAGE_SIZE,
            "offset": offset,
        }
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        page = r.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def fetch_year(year: int) -> pd.DataFrame:
    df = pd.DataFrame([row for term in API_TERMS for row in fetch_term(year, term)])
    df = df.drop_duplicates(subset=["Prscrbr_Geo_Lvl", "Prscrbr_Geo_Cd", "Brnd_Name", "Gnrc_Name"])
    text = df["Gnrc_Name"].fillna("") + " | " + df["Brnd_Name"].fillna("")
    df = df[text.str.contains(STIMULANT_RE, na=False)].copy()
    df.insert(0, "Year", year)
    df["Source_Dataset_UUID"] = DATASETS[year]
    return df


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["GE65_Sprsn_Flag", "GE65_Bene_Sprsn_Flag", "Prscrbr_Geo_Cd"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["Ingredient_Family"] = [ingredient_family(g, b) for g, b in zip(df["Gnrc_Name"], df["Brnd_Name"])]
    # Under-65 = all ages minus 65+; left blank wherever the 65+ value is suppressed.
    for m in ["Clms", "30day_Fills", "Drug_Cst", "Benes"]:
        df[f"LT65_Tot_{m}"] = df[f"Tot_{m}"] - df[f"GE65_Tot_{m}"]
    cols = [
        "Year", "Prscrbr_Geo_Lvl", "Prscrbr_Geo_Cd", "Prscrbr_Geo_Desc",
        "Ingredient_Family", "Gnrc_Name", "Brnd_Name",
        "Tot_Prscrbrs", "Tot_Clms", "Tot_30day_Fills", "Tot_Drug_Cst", "Tot_Benes",
        "GE65_Sprsn_Flag", "GE65_Tot_Clms", "GE65_Tot_30day_Fills", "GE65_Tot_Drug_Cst",
        "GE65_Bene_Sprsn_Flag", "GE65_Tot_Benes",
        "LT65_Tot_Clms", "LT65_Tot_30day_Fills", "LT65_Tot_Drug_Cst", "LT65_Tot_Benes",
        "LIS_Bene_Cst_Shr", "NonLIS_Bene_Cst_Shr", "Source_Dataset_UUID",
    ]
    return df[cols].sort_values(["Year", "Prscrbr_Geo_Lvl", "Prscrbr_Geo_Desc", "Gnrc_Name", "Brnd_Name"])


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, default=min(DATASETS))
    ap.add_argument("--end", type=int, default=max(DATASETS))
    ap.add_argument("--out", default=str(here / "data" / "medicare_partd_stimulant_prescribing_2013_2024.csv"))
    args = ap.parse_args()

    frames = []
    for year in range(args.start, args.end + 1):
        df = fetch_year(year)
        print(f"{year}: {len(df):,} stimulant rows")
        frames.append(df)
    out_df = tidy(pd.concat(frames, ignore_index=True))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    print(f"\nWrote {len(out_df):,} rows to {out.resolve()}")


if __name__ == "__main__":
    main()
