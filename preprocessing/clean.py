"""Data cleaning: missing values, noisy data, outliers. Decisions and results: README, section Data cleaning.

Usage (from the repository root):  python preprocessing/clean.py
Input:  data/intermediate/jobs.csv
Output: data/intermediate/jobs_clean.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "intermediate" / "jobs.csv"
OUT = ROOT / "data" / "intermediate" / "jobs_clean.csv"

MIN_WAGE_HOUR = 7.25            # US federal minimum wage
MIN_WAGE_YEAR = 7.25 * 2080     # 40 hours x 52 weeks
MAX_INFERRED_HOUR = 100         # an "hourly" amount this high was guessed from a typo, not stated
NOT_PAY = r"revenue|\$\s?\d+\+?\s?(?:million|MM)\b|funding for compute"
UNKNOWN = ["seniority", "work_mode", "employment_type", "degree", "states", "cities"]
TITLE_FIXES = {
    r"\s*[–—]\s*": " - ",       # en and em dashes
    r"\bSr\.?\s": "Senior ",
    r"\bJr\.?\s": "Junior ",
    r"\bMgr\b\.?": "Manager",
    r"\s+": " ",
}


def drop(df, mask, reason):
    print(f"  {reason}: {mask.sum()} rows dropped")
    return df[~mask]


def main():
    df = pd.read_csv(IN)
    print(f"read {len(df)} rows from {IN.relative_to(ROOT)}")

    print("1. missing values: the target")
    df = drop(df, df["salary_min"].isna(), "no salary")

    print("2. noisy data: wrong salaries")
    df = drop(df, df["salary_currency"] != "USD", "not in USD")
    df = drop(df, df["salary_text"].str.contains(NOT_PAY, case=False), "amount that is not pay")
    df = drop(df, (df["salary_period"] == "hour") & (df["salary_min"] < MIN_WAGE_HOUR), "below the minimum wage (hour)")
    df = drop(df, (df["salary_period"] == "year") & (df["salary_min"] < MIN_WAGE_YEAR), "below the minimum wage (year)")
    df = drop(df, (df["salary_period"] == "hour") & (df["salary_period_source"] == "inferred")
              & (df["salary_min"] >= MAX_INFERRED_HOUR), "inferred hourly amount of $100 or more")

    print("3. missing values: the features")
    print(f"  salary_max filled with salary_min: {df['salary_max'].isna().sum()} rows")
    df["salary_max"] = df["salary_max"].fillna(df["salary_min"])
    for col in UNKNOWN:
        print(f"  {col} filled with 'unknown': {df[col].isna().sum()} rows")
        df[col] = df[col].fillna("unknown")
    df = df.drop(columns=["office_days", "detail_error"])
    print("  columns dropped: office_days, detail_error")

    print("4. outliers: 1.5 IQR per pay period (counted, not removed)")
    for period, group in df.groupby("salary_period"):
        s = group["salary_min"]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        top = group.loc[s > high, "company"].value_counts().head(3).to_dict()
        print(f"  {period}: {((s < low) | (s > high)).sum()} of {len(s)} outside [{low:,.0f}, {high:,.0f}]; most above: {top}")

    print("5. noisy data: titles")
    before = df["title"].nunique()
    for pattern, replacement in TITLE_FIXES.items():
        df["title"] = df["title"].str.replace(pattern, replacement, regex=True)
    df["title"] = df["title"].str.strip()
    print(f"  distinct titles: {before} -> {df['title'].nunique()}")

    # checks of the result
    assert df["salary_min"].notna().all() and (df["salary_currency"] == "USD").all()
    assert (df["salary_max"] >= df["salary_min"]).all()
    assert df[UNKNOWN].notna().all().all()

    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
