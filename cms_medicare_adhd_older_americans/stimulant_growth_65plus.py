#!/usr/bin/env python3
"""
Trends in Medicare Part D stimulant prescribing and cost for beneficiaries 65+.

Input:
  data/medicare_partd_stimulant_prescribing_2013_2024.csv, built by
  build_stimulant_prescribing_dataset.py from CMS "Medicare Part D
  Prescribers - by Geography and Drug". National rows only.

Limitations:
  1) Beneficiary counts are unique within a drug row. Summing across
     stimulant products double-counts people who used more than one product,
     so the class total is labeled Bene_Product_Counts. It is an upper
     bound on the number of 65+ stimulant users, not a unique count; no
     public CMS file provides one. Claims and 30-day fills are additive and
     are the preferred volume measures.
  2) Raw counts, not rates: growth partly reflects growth in the number of
     Medicare Part D enrollees aged 65+.
  3) Drug cost is CMS gross drug cost (Medicare, plan, beneficiary and other
     payments) before confidential manufacturer rebates/price concessions.
     Real costs are restated in 2024 dollars with annual-average CPI-U.
  4) GE65 values are suppressed for a handful of rare products each year
     (fewer than 11 claims or beneficiaries), so 65+ totals are a slight
     undercount; the script reports how many rows were suppressed.

Usage:
  python stimulant_growth_65plus.py
  python stimulant_growth_65plus.py --data my.csv --out growth.xlsx
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

# BLS CPI-U, U.S. city average, all items, annual average (series CUUR0000SA0).
CPI_U = {
    2013: 232.957, 2014: 236.736, 2015: 237.017, 2016: 240.007,
    2017: 245.120, 2018: 251.107, 2019: 255.657, 2020: 258.811,
    2021: 270.970, 2022: 292.655, 2023: 304.702, 2024: 313.689,
}
CPI_BASE_YEAR = 2024

# (label, start, end) windows reported in the Growth sheet.
WINDOWS = [("2013-2024", 2013, 2024), ("2013-2019", 2013, 2019), ("2019-2024", 2019, 2024)]


def annual_summary(nat: pd.DataFrame) -> pd.DataFrame:
    g = nat.groupby("Year")
    s = pd.DataFrame({
        "GE65_Claims": g["GE65_Tot_Clms"].sum(),
        "GE65_30day_Fills": g["GE65_Tot_30day_Fills"].sum(),
        "GE65_Bene_Product_Counts": g["GE65_Tot_Benes"].sum(),
        "GE65_Drug_Cost": g["GE65_Tot_Drug_Cst"].sum(),
        "LT65_Claims": g["LT65_Tot_Clms"].sum(),
        "LT65_Drug_Cost": g["LT65_Tot_Drug_Cst"].sum(),
        "All_Ages_Claims": g["Tot_Clms"].sum(),
        "All_Ages_Drug_Cost": g["Tot_Drug_Cst"].sum(),
        "Product_Rows": g.size(),
        "GE65_Suppressed_Rows": g.apply(lambda d: (d["GE65_Sprsn_Flag"].ne("") | d["GE65_Bene_Sprsn_Flag"].ne("")).sum()),
    }).reset_index()
    deflator = s["Year"].map(lambda y: CPI_U[CPI_BASE_YEAR] / CPI_U[y])
    s[f"GE65_Drug_Cost_Real{CPI_BASE_YEAR}"] = s["GE65_Drug_Cost"] * deflator
    s["GE65_Cost_per_Claim"] = s["GE65_Drug_Cost"] / s["GE65_Claims"]
    s["GE65_Cost_per_30day_Fill"] = s["GE65_Drug_Cost"] / s["GE65_30day_Fills"]
    s[f"GE65_Cost_per_30day_Fill_Real{CPI_BASE_YEAR}"] = s["GE65_Cost_per_30day_Fill"] * deflator
    s["GE65_Share_of_Claims"] = s["GE65_Claims"] / s["All_Ages_Claims"]
    s["GE65_Share_of_Cost"] = s["GE65_Drug_Cost"] / s["All_Ages_Drug_Cost"]
    for c in ["GE65_Claims", "GE65_30day_Fills", "GE65_Drug_Cost", f"GE65_Drug_Cost_Real{CPI_BASE_YEAR}"]:
        s[f"YoY_{c}"] = s[c].pct_change()
    return s


def growth_table(annual: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "GE65_Claims", "GE65_30day_Fills", "GE65_Bene_Product_Counts",
        "GE65_Drug_Cost", f"GE65_Drug_Cost_Real{CPI_BASE_YEAR}",
        "GE65_Cost_per_30day_Fill", f"GE65_Cost_per_30day_Fill_Real{CPI_BASE_YEAR}",
        "LT65_Claims", "LT65_Drug_Cost", "All_Ages_Claims", "All_Ages_Drug_Cost",
    ]
    a = annual.set_index("Year")
    rows = []
    for m in metrics:
        row = {"Metric": m}
        for label, y0, y1 in WINDOWS:
            if y0 in a.index and y1 in a.index:
                v0, v1 = a.at[y0, m], a.at[y1, m]
                row[f"Pct_Change_{label}"] = v1 / v0 - 1
                row[f"CAGR_{label}"] = (v1 / v0) ** (1 / (y1 - y0)) - 1
        rows.append(row)
    return pd.DataFrame(rows)


def ingredient_table(nat: pd.DataFrame) -> pd.DataFrame:
    t = (nat.groupby(["Year", "Ingredient_Family"])
            [["GE65_Tot_Clms", "GE65_Tot_30day_Fills", "GE65_Tot_Drug_Cst"]].sum().reset_index())
    t["GE65_Cost_per_30day_Fill"] = t["GE65_Tot_Drug_Cst"] / t["GE65_Tot_30day_Fills"]
    t["Share_of_GE65_Claims"] = t["GE65_Tot_Clms"] / t.groupby("Year")["GE65_Tot_Clms"].transform("sum")
    t["Share_of_GE65_Cost"] = t["GE65_Tot_Drug_Cst"] / t.groupby("Year")["GE65_Tot_Drug_Cst"].transform("sum")
    return t


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(here / "data" / "medicare_partd_stimulant_prescribing_2013_2024.csv"))
    ap.add_argument("--out", default=str(here / "stimulant_growth_65plus.xlsx"))
    args = ap.parse_args()

    df = pd.read_csv(args.data, dtype={"Prscrbr_Geo_Cd": str, "GE65_Sprsn_Flag": str, "GE65_Bene_Sprsn_Flag": str})
    df[["GE65_Sprsn_Flag", "GE65_Bene_Sprsn_Flag"]] = df[["GE65_Sprsn_Flag", "GE65_Bene_Sprsn_Flag"]].fillna("")
    nat = df[df["Prscrbr_Geo_Lvl"] == "National"]

    annual = annual_summary(nat)
    growth = growth_table(annual)
    ingredient = ingredient_table(nat)

    with pd.ExcelWriter(Path(args.out), engine="xlsxwriter") as writer:
        growth.to_excel(writer, sheet_name="Growth", index=False)
        annual.to_excel(writer, sheet_name="Annual_65plus", index=False)
        ingredient.to_excel(writer, sheet_name="Ingredient_Year_65plus", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
    print(f"Wrote {Path(args.out).resolve()}\n")
    print(annual[["Year", "GE65_Claims", "GE65_30day_Fills", "GE65_Drug_Cost",
                  f"GE65_Drug_Cost_Real{CPI_BASE_YEAR}", "GE65_Cost_per_30day_Fill",
                  "LT65_Claims", "GE65_Share_of_Claims", "GE65_Suppressed_Rows"]].to_string(index=False))
    print()
    print(growth.to_string(index=False))
    print()
    print(ingredient.pivot(index="Ingredient_Family", columns="Year", values="GE65_Cost_per_30day_Fill").to_string())


if __name__ == "__main__":
    main()
