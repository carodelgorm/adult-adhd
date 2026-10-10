# Stimulant prescribing to older Americans in Medicare Part D

Reproducible analysis of Schedule II ADHD stimulant prescribing and gross drug
cost in Medicare Part D, with a focus on beneficiaries aged 65 and older,
2013–2024. All inputs are public CMS data downloaded by the scripts.

**Drugs included:** amphetamine, dextroamphetamine, mixed amphetamine salts,
lisdexamfetamine, methylphenidate, dexmethylphenidate, serdexmethylphenidate
and methamphetamine. Non-stimulant ADHD drugs (atomoxetine, guanfacine,
clonidine, viloxazine) and modafinil/armodafinil are excluded.

## Data sources

| CMS dataset | Years | Age detail | Used for |
|---|---|---|---|
| [Medicare Part D Prescribers – by Geography and Drug](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug) | 2013–2024 | All ages and 65+ | 65+ prescribing and cost trends |
| [Medicare Part D Spending by Drug](https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug) | 2019–2024 | All ages only | All-ages spending, dosage units |

## Repository layout

```
requirements.txt
cms_medicare_adhd_older_americans/
├── build_stimulant_prescribing_dataset.py      # 1. download → clean/ dataset
├── stimulant_growth_65plus.py                  # 2. clean/ dataset → out/ 65+ trends
├── build_medicare_partd_stimulant_2019_2024.py # 3. all-ages spending → out/
├── util/env.py                                 # project paths
├── clean/
│   ├── medicare_partd_stimulant_prescribing_2013_2024.csv  # analysis-ready dataset
│   └── README.md                                           # data dictionary
└── out/
    ├── stimulant_growth_65plus.xlsx            # 65+ growth, annual and by-ingredient tables
    └── medicare_partd_stimulant_2019_2024.xlsx # all-ages spending tables
```

The built dataset and workbooks are committed, so you can use them without
running anything. See [`clean/README.md`](cms_medicare_adhd_older_americans/clean/README.md)
for column definitions and caveats.

## Running it

Requires Python 3.11+ and an internet connection to data.cms.gov.

With conda:

```bash
conda create -n adult-adhd python=3.13
conda activate adult-adhd
pip install -r requirements.txt
```

Or with a plain virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then, from the repository root:

```bash
cd cms_medicare_adhd_older_americans
python build_stimulant_prescribing_dataset.py    # ~1 min; writes clean/…csv
python stimulant_growth_65plus.py                # reads clean/, writes out/stimulant_growth_65plus.xlsx
python build_medicare_partd_stimulant_2019_2024.py   # downloads two large CSVs; writes out/medicare_partd_stimulant_2019_2024.xlsx
```

Step 2 depends on step 1. Step 3 is independent. Each script accepts `--help`.
Output folders can be redirected with the `ADHD_CLEAN_DIR` and `ADHD_OUT_DIR`
environment variables (see `util/env.py`).

## Caveats

- **65+ is the only age split CMS publishes** at the drug level. Finer age
  bands require beneficiary-level Part D event data (ResDAC).
- **Beneficiary counts are not unique across products.** Summing them
  double-counts people using more than one stimulant, so totals are labeled
  `Bene_Product_Counts` and are an upper bound. Claims and 30-day fills are
  the preferred volume measures.
- **Costs are gross**, before confidential manufacturer rebates. Real-dollar
  figures use annual-average CPI-U (2024 = base).
- **Counts are not population-adjusted**; part of the growth reflects growth in
  Part D enrollment among people 65+.
- **The two CMS files are built differently**, so all-ages totals agree closely
  but not exactly.
