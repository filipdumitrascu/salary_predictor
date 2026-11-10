"""Data reduction: attribute selection, PCA, sampling. Decisions and results: README, section Data reduction.

Usage (from the repository root):  python preprocessing/reduce.py
Input:  data/intermediate/train_transformed.csv, test_transformed.csv
Output: data/processed/train.csv, data/processed/test.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "intermediate"
OUT = ROOT / "data" / "processed"

TARGET = ["salary", "log_salary"]
NOT_FEATURES = {
    "identifiers and checks": ["url", "title", "cities", "salary_text", "seniority_source", "salary_period_source", "description_chars"],
    "the target before it was built": ["salary_min", "salary_max"],
    "one value only": ["salary_currency"],
    "known only from the salary (leakage)": ["salary_period"],
    "almost one value (99% 'US')": ["countries"],
}
MIN_ONES = 20      # a 0/1 column with fewer 1s in train is too rare to learn from
MAX_CORR = 0.95    # of two columns more correlated than this, the second is dropped


def main():
    train = pd.read_csv(IN / "train_transformed.csv")
    test = pd.read_csv(IN / "test_transformed.csv")
    print(f"read train {train.shape}, test {test.shape}")

    print("1. attribute selection: columns that are not features")
    for reason, cols in NOT_FEATURES.items():
        print(f"  {reason}: {cols}")
    dropped = [c for cols in NOT_FEATURES.values() for c in cols]
    features = [c for c in train.columns if c not in dropped + TARGET + ["job_id"]]
    print(f"  features left: {len(features)}")

    print(f"2. attribute selection: low variance (0/1 columns with fewer than {MIN_ONES} ones in train)")
    binary = [c for c in features if set(train[c].unique()) <= {0, 1}]
    ones = train[binary].sum()
    rare = ones[ones < MIN_ONES].index.tolist()
    print(f"  {len(rare)} dropped: {rare}")
    features = [c for c in features if c not in rare]

    print(f"3. attribute selection: redundant pairs (|Pearson| > {MAX_CORR} in train)")
    corr = train[features].corr().abs()
    redundant = []
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            if a not in redundant and b not in redundant and corr.loc[a, b] > MAX_CORR:
                print(f"  {a} / {b}: {corr.loc[a, b]:.3f} -> {b} dropped")
                redundant.append(b)
    features = [c for c in features if c not in redundant]

    print("4. relevance: correlation of each feature with log_salary in train (printed, nothing dropped)")
    r = train[features].corrwith(train["log_salary"]).sort_values(key=abs, ascending=False)
    print(f"  strongest: {r.head(8).round(2).to_dict()}")
    print(f"  |r| < 0.01: {(r.abs() < 0.01).sum()} features")

    print("5. PCA on the standardized features of train (printed, not applied)")
    x = train[features]
    z = (x - x.mean()) / x.std()
    singular = np.linalg.svd(z.to_numpy(), compute_uv=False)
    explained = singular ** 2 / (singular ** 2).sum()
    needed = {share: int((explained.cumsum() < share).sum() + 1) for share in (0.80, 0.90, 0.95)}
    print(f"  first 3 components explain {explained[:3].round(3).tolist()}")
    print(f"  components needed: {needed} of {len(features)} features")

    print("6. numerosity reduction: sampling (printed, not applied)")
    share = train["company_amazon"].mean()
    print(f"  amazon is {share:.1%} of train; rows kept as they are")

    # checks of the result
    assert train[features].notna().all().all() and test[features].notna().all().all()
    assert not set(features) & set(dropped + TARGET)

    OUT.mkdir(parents=True, exist_ok=True)
    columns = ["job_id"] + features + TARGET
    train[columns].to_csv(OUT / "train.csv", index=False)
    test[columns].to_csv(OUT / "test.csv", index=False)
    print(f"wrote train {train[columns].shape}, test {test[columns].shape} -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
