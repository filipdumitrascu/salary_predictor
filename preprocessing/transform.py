"""Data transformation: target, feature construction, encoding, normalization. Decisions and results: README, section Data transformation.

Usage (from the repository root):  python preprocessing/transform.py
Input:  data/intermediate/jobs_integrated.csv
Output: data/intermediate/train_transformed.csv, data/intermediate/test_transformed.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "intermediate" / "jobs_integrated.csv"
OUT = ROOT / "data" / "intermediate"

SEP = " | "
CRAWL_DAY = pd.Timestamp("2026-11-05")  # collected_date (one value, dropped at integration)
TEST_SHARE, SEED = 0.2, 42
ORDINAL = {
    "seniority": ["intern", "entry", "mid", "senior", "staff", "lead", "director"],
    "degree": ["bachelor", "master", "phd"],
    "work_mode": ["remote", "hybrid", "onsite"],
    "employment_type": ["contract", "part-time", "full-time"],
}
ONE_HOT = ["company", "industry", "role_family"]
MULTI_HOT = {"skills": "skill_", "states": "state_"}
NUMERIC = ["years_min", "years_max", "days_old", "n_locations", "n_skills"]
SKEWED = ["days_old", "n_locations"]  # long right tail: log(1 + x) before z-score


def multi_hot(df, col, prefix):
    """One 0/1 column per value of a column with several values per cell."""
    values = df[col].str.split(SEP, regex=False).explode()
    return pd.crosstab(values.index, values).add_prefix(prefix).reindex(df.index, fill_value=0)


def main():
    df = pd.read_csv(IN)
    print(f"read {len(df)} rows from {IN.relative_to(ROOT)}")

    print("1. target")
    df["salary"] = (df["salary_min"] + df["salary_max"]) / 2
    df["log_salary"] = np.log(df["salary"])
    print(f"  salary = middle of the range; skewness {df['salary'].skew():.2f} -> log_salary {df['log_salary'].skew():.2f}")

    print("2. feature construction")
    df["days_old"] = (CRAWL_DAY - pd.to_datetime(df["posted_date"])).dt.days
    df["n_skills"] = df["skills"].str.split(SEP, regex=False).str.len().fillna(0).astype(int)
    print(f"  days_old (from posted_date): median {df['days_old'].median():.0f}; n_skills: median {df['n_skills'].median():.0f}")

    print("3. encoding")
    for col, order in ORDINAL.items():
        df[col] = df[col].map({value: i for i, value in enumerate(order)})  # "unknown" -> NaN, filled after the split
    print(f"  ordinal -> position in the order: {list(ORDINAL)}")
    parts = [df]
    for col in ONE_HOT:
        parts.append(pd.get_dummies(df[col], prefix=col, dtype=int))
    for col, prefix in MULTI_HOT.items():
        parts.append(multi_hot(df, col, prefix))
    df = pd.concat(parts, axis=1).drop(columns=ONE_HOT + list(MULTI_HOT) + ["posted_date"])
    for col in ONE_HOT + list(MULTI_HOT):
        print(f"  {col}: {df.columns.str.startswith(MULTI_HOT.get(col, col + '_')).sum()} columns of 0/1")

    print("4. train / test split")
    train = df.sample(frac=1 - TEST_SHARE, random_state=SEED)
    test = df.drop(train.index)
    print(f"  train {len(train)}, test {len(test)}; every value below is computed on train only")

    print("5. missing values left from cleaning: train median + a 0/1 column 'was missing'")
    for col in list(ORDINAL) + ["years_min", "years_max", "days_old"]:
        median = train[col].quantile(0.5, interpolation="lower")  # a value that exists (a category, for ordinals)
        for part in (train, test):
            part[f"{col}_missing"] = part[col].isna().astype(int)
            part[col] = part[col].fillna(median)
        print(f"  {col}: {train[f'{col}_missing'].sum()} train rows filled with {median:g}")

    print("6. normalization")
    for col in SKEWED:
        for part in (train, test):
            part[col] = np.log1p(part[col])
    for col in ORDINAL:  # min-max to [0, 1]
        low, high = train[col].min(), train[col].max()
        for part in (train, test):
            part[col] = (part[col] - low) / (high - low)
    print(f"  min-max to [0, 1]: {list(ORDINAL)}")
    for col in NUMERIC:  # z-score: mean 0, std 1
        mean, std = train[col].mean(), train[col].std()
        for part in (train, test):
            part[col] = (part[col] - mean) / std
        print(f"  z-score {col}: train mean {train[col].mean():.2f} std {train[col].std():.2f},"
              f" test mean {test[col].mean():.2f} std {test[col].std():.2f}")

    # checks of the result
    for part in (train, test):
        assert part[list(ORDINAL) + NUMERIC].notna().all().all()
        assert part[list(ORDINAL)].min().min() >= 0 and part[list(ORDINAL)].max().max() <= 1
    assert not set(train["job_id"]) & set(test["job_id"])

    train.to_csv(OUT / "train_transformed.csv", index=False)
    test.to_csv(OUT / "test_transformed.csv", index=False)
    print(f"wrote {train.shape} and {test.shape} -> {OUT.relative_to(ROOT)}/train_transformed.csv, test_transformed.csv")


if __name__ == "__main__":
    main()
