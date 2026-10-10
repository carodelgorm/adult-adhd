#!/usr/bin/env python3
"""
Build a reproducible 2019-2024 Medicare Part D stimulant spending dataset.

Scope:
  Schedule II stimulant ingredients commonly used for ADHD:
  amphetamine / dextroamphetamine products, lisdexamfetamine,
  methylphenidate / dexmethylphenidate products, serdexmethylphenidate
  combinations, and methamphetamine.

Important limitations:
  1) CMS Medicare Part D Spending by Drug is NOT age-restricted. It includes
     Part D beneficiaries under 65 who qualify through disability/ESRD.
     Do not describe these totals as "65+ spending." For 65+ figures use
     build_stimulant_prescribing_dataset.py, which draws on CMS Part D
     Prescribers by Geography and Drug; that file reports claims, 30-day
     fills, cost and beneficiaries for 65+ separately (GE65_* fields).
  2) CMS gross drug cost includes Medicare, plan, beneficiary, and other
     payments and does not subtract manufacturer rebates/price concessions.
  3) Tot_Benes is a unique beneficiary count within a drug/product row, but
     summing Tot_Benes across products double-counts people who used >1
     stimulant product. The script labels the sum "beneficiary-product counts."
  4) This CMS spending file reports dosage units, not days supplied.
  5) 2019 is taken from an archived historical CMS release because the current
     CMS file exposes only the most recent five years. The default historical
     URL below is a public mirror of the CMS release archived by Data Rescue
     Project/DataLumos. For maximum provenance, download the exact historical
     CMS CSV from the DataLumos archive and pass it with --historical-csv.

Usage:
  python build_medicare_partd_stimulant_2019_2024.py
  python build_medicare_partd_stimulant_2019_2024.py --out my_output.xlsx
  python build_medicare_partd_stimulant_2019_2024.py --historical-csv /path/to/DSD_PTD_RY24_P04_V10_DY22_BGM.csv
"""

from __future__ import annotations
import argparse
import io
import re
from pathlib import Path
import requests
import pandas as pd
import numpy as np

CURRENT_CSV = (
    "https://data.cms.gov/sites/default/files/2026-06/"
    "98218f98-166c-4723-8438-c344a4ef96a6/"
    "DSD_PTD_RY26_P04_V10_DY24_BGM.csv"
)
CURRENT_PAGE = (
    "https://data.cms.gov/summary-statistics-on-use-and-payments/"
    "medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug"
)

# Public mirror of the historical CMS release archived by Data Rescue Project.
HISTORICAL_MIRROR = (
    "https://raw.githubusercontent.com/bpkindo/datasets/main/"
    "DSD_PTD_RY24_P04_V10_DY22_BGM.csv"
)
HISTORICAL_ARCHIVE = "https://doi.org/10.3886/E227922V1"

STIMULANT_RE = re.compile(
    r"(?:"
    r"amphetamine|dextroamphetamine|lisdexamfetamine|"
    r"methylphenidate|dexmethylphenidate|serdexmethylphenidate|"
    r"methamphetamine"
    r")",
    flags=re.I,
)

def fetch_csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content), low_memory=False)

def read_csv_path_or_url(value: str | None, fallback_url: str) -> pd.DataFrame:
    if value:
        p = Path(value)
        if p.exists():
            return pd.read_csv(p, low_memory=False)
        if value.startswith("http://") or value.startswith("https://"):
            return fetch_csv(value)
        raise FileNotFoundError(value)
    return fetch_csv(fallback_url)

def find_col(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    return None

def overall_only(df: pd.DataFrame) -> pd.DataFrame:
    # CMS releases normally have manufacturer detail plus one "Overall" row
    # for each brand/generic pair. Filtering to Overall avoids double counting.
    mftr = find_col(df, ["Mftr_Name", "Manufacturer_Name"])
    if mftr is None:
        raise KeyError("Could not identify manufacturer-name column.")
    return df[df[mftr].astype(str).str.strip().str.lower().eq("overall")].copy()

def stimulant_only(df: pd.DataFrame) -> pd.DataFrame:
    gnrc = find_col(df, ["Gnrc_Name", "Generic_Name"])
    brnd = find_col(df, ["Brnd_Name", "Brand_Name"])
    if gnrc is None or brnd is None:
        raise KeyError("Could not identify generic/brand columns.")
    text = df[gnrc].fillna("").astype(str) + " | " + df[brnd].fillna("").astype(str)
    return df[text.str.contains(STIMULANT_RE, na=False)].copy()

def ingredient_family(generic_name: str, brand_name: str) -> str:
    s = f"{generic_name} {brand_name}".lower()
    if "serdexmethylphenidate" in s:
        return "Serdexmethylphenidate/dexmethylphenidate"
    if "lisdexamfetamine" in s:
        return "Lisdexamfetamine"
    if "dexmethylphenidate" in s:
        return "Dexmethylphenidate"
    if "methylphenidate" in s:
        return "Methylphenidate"
    if "methamphetamine" in s:
        return "Methamphetamine"
    if "dextroamphetamine" in s and "amphetamine" in s:
        return "Mixed amphetamine salts / amphetamine-dextroamphetamine"
    if "dextroamphetamine" in s:
        return "Dextroamphetamine"
    if "amphetamine" in s:
        return "Amphetamine-family"
    return "Other matched stimulant"

def metric_col(df: pd.DataFrame, prefix: str, year: int):
    # CMS columns use forms such as Tot_Spndng_2024, Tot_Clms_2024, etc.
    want = f"{prefix}_{year}".lower()
    for c in df.columns:
        if c.lower() == want:
            return c
    return None

def extract_long(df: pd.DataFrame, years, release_label, release_url):
    df = stimulant_only(overall_only(df))
    brnd = find_col(df, ["Brnd_Name", "Brand_Name"])
    gnrc = find_col(df, ["Gnrc_Name", "Generic_Name"])
    tot_mftr = find_col(df, ["Tot_Mftr", "Total_Manufacturers"])
    rows = []
    for year in years:
        spend_c = metric_col(df, "Tot_Spndng", year)
        units_c = metric_col(df, "Tot_Dsg_Unts", year)
        clms_c = metric_col(df, "Tot_Clms", year)
        benes_c = metric_col(df, "Tot_Benes", year)
        outlier_c = metric_col(df, "Outlier_Flag", year)
        if not spend_c:
            continue
        for _, r in df.iterrows():
            spend = pd.to_numeric(r.get(spend_c), errors="coerce")
            if pd.isna(spend):
                continue
            brand = str(r.get(brnd, "") or "")
            generic = str(r.get(gnrc, "") or "")
            units = pd.to_numeric(r.get(units_c), errors="coerce") if units_c else np.nan
            claims = pd.to_numeric(r.get(clms_c), errors="coerce") if clms_c else np.nan
            benes = pd.to_numeric(r.get(benes_c), errors="coerce") if benes_c else np.nan
            rows.append({
                "Year": year,
                "Ingredient_Family": ingredient_family(generic, brand),
                "Brand_Name_CMS": brand,
                "Generic_Name_CMS": generic,
                "Total_Manufacturers": pd.to_numeric(r.get(tot_mftr), errors="coerce") if tot_mftr else np.nan,
                "Gross_Drug_Cost": spend,
                "Dosage_Units": units,
                "Claims": claims,
                "Beneficiaries_Product_Row": benes,
                "Gross_Cost_per_Claim": spend / claims if pd.notna(claims) and claims else np.nan,
                "Gross_Cost_per_Dosage_Unit": spend / units if pd.notna(units) and units else np.nan,
                "Gross_Cost_per_Product_Beneficiary": spend / benes if pd.notna(benes) and benes else np.nan,
                "Outlier_Flag": r.get(outlier_c) if outlier_c else None,
                "Source_Release": release_label,
                "Source_URL": release_url,
            })
    return pd.DataFrame(rows)

def annual_summary(detail: pd.DataFrame) -> pd.DataFrame:
    g = detail.groupby("Year", as_index=False).agg(
        Gross_Drug_Cost=("Gross_Drug_Cost", "sum"),
        Claims=("Claims", "sum"),
        Dosage_Units=("Dosage_Units", "sum"),
        Beneficiary_Product_Counts=("Beneficiaries_Product_Row", "sum"),
        Product_Rows=("Generic_Name_CMS", "size"),
    )
    g["Gross_Cost_per_Claim"] = g["Gross_Drug_Cost"] / g["Claims"]
    g["Gross_Cost_per_Dosage_Unit"] = g["Gross_Drug_Cost"] / g["Dosage_Units"]
    g["YoY_Gross_Drug_Cost_Change"] = g["Gross_Drug_Cost"].pct_change()
    g["YoY_Claims_Change"] = g["Claims"].pct_change()
    return g

def ingredient_summary(detail: pd.DataFrame) -> pd.DataFrame:
    g = detail.groupby(["Year", "Ingredient_Family"], as_index=False).agg(
        Gross_Drug_Cost=("Gross_Drug_Cost", "sum"),
        Claims=("Claims", "sum"),
        Dosage_Units=("Dosage_Units", "sum"),
        Beneficiary_Product_Counts=("Beneficiaries_Product_Row", "sum"),
    )
    g["Gross_Cost_per_Claim"] = g["Gross_Drug_Cost"] / g["Claims"]
    g["Gross_Cost_per_Dosage_Unit"] = g["Gross_Drug_Cost"] / g["Dosage_Units"]
    return g

def release_validation(hist_long: pd.DataFrame, current_long: pd.DataFrame):
    overlap = sorted(set(hist_long.Year).intersection(set(current_long.Year)))
    if not overlap:
        return pd.DataFrame()
    a = annual_summary(hist_long[hist_long.Year.isin(overlap)])[["Year","Gross_Drug_Cost","Claims"]]
    b = annual_summary(current_long[current_long.Year.isin(overlap)])[["Year","Gross_Drug_Cost","Claims"]]
    x = a.merge(b, on="Year", suffixes=("_Historical","_Current"))
    x["Spending_Difference_Current_minus_Historical"] = (
        x["Gross_Drug_Cost_Current"] - x["Gross_Drug_Cost_Historical"]
    )
    x["Spending_Percent_Difference"] = (
        x["Spending_Difference_Current_minus_Historical"] / x["Gross_Drug_Cost_Historical"]
    )
    x["Claims_Difference_Current_minus_Historical"] = (
        x["Claims_Current"] - x["Claims_Historical"]
    )
    return x

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="medicare_partd_stimulant_2019_2024.xlsx")
    ap.add_argument(
        "--historical-csv",
        default=None,
        help="Local path or URL for DSD_PTD_RY24_P04_V10_DY22_BGM.csv. "
             "If omitted, uses a public mirror of the archived CMS release."
    )
    args = ap.parse_args()

    print("Downloading current CMS Part D Spending by Drug file...")
    current = fetch_csv(CURRENT_CSV)

    print("Loading historical CMS release for 2019...")
    historical = read_csv_path_or_url(args.historical_csv, HISTORICAL_MIRROR)

    # Current release is authoritative for 2020-2024. Historical release supplies 2019.
    current_long = extract_long(
        current, range(2020, 2025),
        "CMS RY26 / data year through 2024",
        CURRENT_PAGE
    )
    hist_long = extract_long(
        historical, range(2019, 2023),
        "CMS RY24 historical release / data year through 2022",
        HISTORICAL_ARCHIVE
    )

    detail_2019 = hist_long[hist_long.Year.eq(2019)].copy()
    detail_2020_2024 = current_long[current_long.Year.between(2020, 2024)].copy()
    detail = pd.concat([detail_2019, detail_2020_2024], ignore_index=True)
    detail = detail.sort_values(["Year","Ingredient_Family","Generic_Name_CMS","Brand_Name_CMS"])

    annual = annual_summary(detail)
    ingredient = ingredient_summary(detail)
    validation = release_validation(hist_long, current_long)

    sources = pd.DataFrame([
        {
            "Source": "CMS Medicare Part D Spending by Drug",
            "URL": CURRENT_PAGE,
            "Use": "2020-2024 product-level gross drug spending, claims, dosage units, beneficiaries",
            "Notes": "100% final-action Part D claims; gross drug cost excludes confidential rebates/price concessions."
        },
        {
            "Source": "Historical CMS release archived by Data Rescue Project / DataLumos",
            "URL": HISTORICAL_ARCHIVE,
            "Use": "2019 product-level data",
            "Notes": "Used because current CMS release exposes a rolling five-year window."
        },
        {
            "Source": "Public mirror of historical CMS CSV",
            "URL": HISTORICAL_MIRROR,
            "Use": "Default machine-readable fetch for historical release",
            "Notes": "For maximum provenance, download the same named CSV from the archive and pass --historical-csv."
        }
    ])

    readme = pd.DataFrame({
        "Item": [
            "Scope",
            "Not age 65+",
            "Gross vs net spending",
            "Beneficiary counts",
            "Days supplied",
            "2019 provenance",
            "Release overlap",
        ],
        "Explanation": [
            "Schedule II stimulant ingredients commonly used for ADHD; non-stimulants such as atomoxetine, guanfacine, clonidine, and viloxazine are excluded.",
            "The public CMS drug-spending file includes all Part D beneficiaries, including some under 65. These totals must not be labeled 65+ spending. For 65+ figures, see build_stimulant_prescribing_dataset.py (CMS Part D Prescribers by Geography and Drug, GE65_* fields).",
            "Gross drug cost includes Medicare, plan, beneficiary and other payments and does not subtract manufacturer rebates/price concessions.",
            "Beneficiary counts are unique within a product row. Summing them across stimulant products double-counts beneficiaries using multiple products, so the class-level field is labeled Beneficiary_Product_Counts. No public CMS file gives a unique count of stimulant users across products, for any age group.",
            "This CMS file reports dosage units, not days supplied. A different Part D prescriber dataset is needed for days supplied.",
            "2019 comes from an archived historical CMS release because the current file is a rolling five-year release.",
            "The workbook includes a release-validation sheet comparing overlapping 2020-2022 totals across CMS release vintages."
        ]
    })

    out = Path(args.out)
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        annual.to_excel(writer, sheet_name="Annual_Summary", index=False)
        ingredient.to_excel(writer, sheet_name="Ingredient_Year", index=False)
        detail.to_excel(writer, sheet_name="Product_Detail", index=False)
        validation.to_excel(writer, sheet_name="Release_Validation", index=False)
        readme.to_excel(writer, sheet_name="README", index=False)
        sources.to_excel(writer, sheet_name="Sources", index=False)

        wb = writer.book
        money_fmt = wb.add_format({"num_format": "$#,##0"})
        money2_fmt = wb.add_format({"num_format": "$#,##0.00"})
        int_fmt = wb.add_format({"num_format": "#,##0"})
        pct_fmt = wb.add_format({"num_format": "0.0%"})
        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1})

        for sheet_name, df in [
            ("Annual_Summary", annual),
            ("Ingredient_Year", ingredient),
            ("Product_Detail", detail),
            ("Release_Validation", validation),
            ("README", readme),
            ("Sources", sources),
        ]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            for col_idx, col in enumerate(df.columns):
                width = min(max(len(str(col)) + 2, 12), 42)
                if len(df):
                    sample_width = min(42, max(len(str(x)) for x in df[col].head(250).fillna("")) + 2)
                    width = max(width, sample_width)
                ws.set_column(col_idx, col_idx, width)
                ws.write(0, col_idx, col, header_fmt)
                if "Cost" in col or "Spnd" in col or "Spending" in col:
                    ws.set_column(col_idx, col_idx, width, money2_fmt if "per_" in col else money_fmt)
                elif col.startswith("YoY_") or "Percent" in col:
                    ws.set_column(col_idx, col_idx, width, pct_fmt)
                elif col in {"Claims","Dosage_Units","Beneficiary_Product_Counts","Beneficiaries_Product_Row","Product_Rows"}:
                    ws.set_column(col_idx, col_idx, width, int_fmt)

    print(f"Wrote {out.resolve()}")
    print("\nAnnual summary:")
    print(annual.to_string(index=False))

if __name__ == "__main__":
    main()
