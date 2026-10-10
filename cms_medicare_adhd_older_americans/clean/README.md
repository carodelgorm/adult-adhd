# Medicare Part D stimulant prescribing, 2013–2024

`medicare_partd_stimulant_prescribing_2013_2024.csv` is built by
`../build_stimulant_prescribing_dataset.py` from CMS
[Medicare Part D Prescribers – by Geography and Drug](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug),
one CMS release per data year.

**Scope:** Schedule II stimulants commonly used for ADHD — amphetamine,
dextroamphetamine, mixed amphetamine salts, lisdexamfetamine, methylphenidate,
dexmethylphenidate, serdexmethylphenidate and methamphetamine. Non-stimulants
(atomoxetine, guanfacine, clonidine, viloxazine) and modafinil/armodafinil are excluded.

**Grain:** one row per `Year` × prescriber geography × brand/generic product.
Geography is the **prescriber's** location, not the beneficiary's.

## Columns

| Column | Meaning |
|---|---|
| `Year` | Data (service) year |
| `Prscrbr_Geo_Lvl` | `National` or `State` |
| `Prscrbr_Geo_Cd`, `Prscrbr_Geo_Desc` | State FIPS code and name (blank / "National" for national rows); also includes territories, Armed Forces, "Foreign Country" and "Unknown" |
| `Ingredient_Family` | Grouping assigned by this repo (see `ingredient_family()` in the spending build script) |
| `Gnrc_Name`, `Brnd_Name` | CMS generic and brand names |
| `Tot_Prscrbrs` | Prescribers with at least one claim for the product |
| `Tot_Clms` | Part D claims, including refills (all ages) |
| `Tot_30day_Fills` | Claims standardized to 30-day supplies |
| `Tot_Drug_Cst` | Gross drug cost: ingredient cost + dispensing fee + sales tax, paid by plan, beneficiary and others; **before** manufacturer rebates |
| `Tot_Benes` | Unique beneficiaries **within this product row** |
| `GE65_*` | Same measures restricted to beneficiaries aged 65+ |
| `GE65_Sprsn_Flag`, `GE65_Bene_Sprsn_Flag` | CMS suppression flags: `*` = fewer than 11; `#` = suppressed so a small under-65 count can't be backed out. When set, the GE65 value is blank |
| `LT65_*` | Derived here: all-ages minus 65+. Blank when the 65+ value is suppressed |
| `LIS_Bene_Cst_Shr`, `NonLIS_Bene_Cst_Shr` | Beneficiary out-of-pocket cost, low-income-subsidy vs non-LIS (all ages) |
| `Source_Dataset_UUID` | data.cms.gov dataset the row came from |

## Caveats

- **Do not sum `Tot_Benes` / `GE65_Tot_Benes` across products** and call it a
  patient count — someone using two products is counted twice. Claims and
  30-day fills are additive.
- **Do not add National and State rows together** — national rows already
  include every state. State rows sum to ~99.7–99.96% of national because of
  small-cell suppression.
- Counts are not population-adjusted; growth partly reflects growth in Part D
  enrollment.
- This prescriber-based file is built differently from the Part D Spending by
  Drug file, so totals will not match it exactly.
