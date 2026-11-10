"""Data integration: duplicates, inconsistencies between sources, redundancy. Decisions and results: README, section Data integration.

Usage (from the repository root):  python preprocessing/integrate.py
Input:  data/intermediate/jobs_clean.csv
Output: data/intermediate/jobs_integrated.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "intermediate" / "jobs_clean.csv"
OUT = ROOT / "data" / "intermediate" / "jobs_integrated.csv"

SAME_JOB = ["company", "title", "salary_min", "salary_max", "description_chars"]
TO_YEAR = {"year": 1, "month": 12, "hour": 2080}  # 2,080 = 40 hours x 52 weeks
SENIORITY = ["intern", "entry", "mid", "senior", "staff", "lead", "director"]
SOURCE_MISSING = ["work_mode", "seniority", "employment_type", "degree", "states"]
NOMINAL_PAIRS = [("company", "industry"), ("seniority", "role_family"), ("seniority", "degree"), ("role_family", "degree")]


def cramers_v(df, a, b):
    """Chi-square of the contingency table of a and b, and Cramer's V = sqrt(chi2 / (n (k - 1))), 0..1."""
    known = df[(df[a] != "unknown") & (df[b] != "unknown")]
    observed = pd.crosstab(known[a], known[b])
    n = observed.values.sum()
    expected = observed.sum(axis=1).values[:, None] * observed.sum(axis=0).values[None, :] / n
    chi2 = ((observed.values - expected) ** 2 / expected).sum()
    return chi2, (chi2 / (n * (min(observed.shape) - 1))) ** 0.5


def main():
    df = pd.read_csv(IN)
    print(f"read {len(df)} rows from {IN.relative_to(ROOT)}")

    print("1. duplicates")
    print(f"  exact (every column equal): {df.duplicated().sum()} rows dropped")
    df = df.drop_duplicates()
    print(f"  same job_id left with different values: {df['job_id'].duplicated().sum()}")
    # shortcut: the copy kept loses the other copies' cities; merge their locations if the city matters more
    partial = df.sort_values("posted_date", ascending=False).duplicated(SAME_JOB)
    print(f"  partial (same company, title, salary, description length): {partial.sum()} rows dropped;"
          f" by company: {df.loc[partial[partial].index, 'company'].value_counts().head(5).to_dict()}")
    df = df.drop(partial[partial].index)

    print("2. inconsistencies: value conflicts between sources")
    factor = df["salary_period"].map(TO_YEAR)
    print(f"  salary converted to a year: {(factor > 1).sum()} rows ({df['salary_period'].value_counts().to_dict()})")
    df["salary_min"] = df["salary_min"] * factor
    df["salary_max"] = df["salary_max"] * factor
    before = df["countries"].nunique()
    df["countries"] = df["countries"].str.split(" | ", regex=False).apply(lambda c: " | ".join(sorted(c)))
    print(f"  countries sorted: {before} -> {df['countries'].nunique()} distinct values")
    print("  share of 'unknown' per company (companies at 100% never give the value):")
    for col in SOURCE_MISSING:
        share = (df[col] == "unknown").groupby(df["company"]).mean()
        print(f"    {col}: {len(share)} companies, {(share == 1).sum()} at 100%: {sorted(share[share == 1].index)}")

    print("3. redundancy: dependencies and correlation")
    assert df.groupby("company")["company_name"].nunique().max() == 1
    assert df.groupby("company_name")["company"].nunique().max() == 1
    print(f"  collected_date: {df['collected_date'].nunique()} distinct value(s)")
    df = df.drop(columns=["company_name", "locations", "collected_date"])
    print("  columns dropped: company_name, locations, collected_date")
    print(f"  Pearson salary_min / salary_max: {df['salary_min'].corr(df['salary_max']):.2f}")
    print(f"  Pearson years_min / years_max:   {df['years_min'].corr(df['years_max']):.2f}")
    seniority = df["seniority"].map({s: i for i, s in enumerate(SENIORITY)})  # position in the order; "unknown" -> NaN
    both = seniority.notna() & df["years_min"].notna()
    rho = seniority[both].rank().corr(df.loc[both, "years_min"].rank())  # Spearman = Pearson on the ranks
    print(f"  Spearman seniority / years_min:  {rho:.2f}")
    for a, b in NOMINAL_PAIRS:
        chi2, v = cramers_v(df, a, b)
        print(f"  chi-square {a} / {b}: {chi2:,.0f}, Cramer's V {v:.2f}")

    # checks of the result
    assert not df.duplicated().any() and not df["job_id"].duplicated().any()
    assert df["salary_min"].notna().all() and (df["salary_max"] >= df["salary_min"]).all()

    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} rows -> {OUT.relative_to(ROOT)}")
    print(f"yearly salary_min: median {df['salary_min'].median():,.0f}, min {df['salary_min'].min():,.0f}, max {df['salary_min'].max():,.0f}")


if __name__ == "__main__":
    main()
