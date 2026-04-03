"""Demo: per-job progress bars with realistic variable-duration data processing."""
import numpy as np
import pandas as pd
from pmap import pmap


def process_chunk(seed: int) -> dict:
    """Simulate a realistic data processing pipeline with variable-size chunks."""
    rng = np.random.default_rng(seed)

    # Variable row count per chunk (5k–500k) drives natural timing differences
    n_rows = rng.integers(50_000, 1_000_000)
    n_features = 20

    df = pd.DataFrame(
        rng.standard_normal((n_rows, n_features)),
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    df["category"] = rng.choice(["A", "B", "C", "D", "E"], size=n_rows)
    df["timestamp"] = pd.date_range("2024-01-01", periods=n_rows, freq="s")

    # Pipeline: clean → engineer features → aggregate
    df = (df
          .assign(**{f"feat_{i}_zscore": lambda d, i=i: (d[f"feat_{i}"] - d[f"feat_{i}"].mean()) / d[f"feat_{i}"].std()
                     for i in range(n_features)})
          .assign(row_mean=lambda d: d[[f"feat_{i}" for i in range(n_features)]].mean(axis=1))
          .assign(row_std=lambda d: d[[f"feat_{i}" for i in range(n_features)]].std(axis=1))
          .assign(rolling_mean=lambda d: d["row_mean"].rolling(100, min_periods=1).mean())
    )

    summary = (df
               .groupby("category")
               .agg(
                   count=("row_mean", "size"),
                   mean=("row_mean", "mean"),
                   std=("row_std", "mean"),
                   rolling_corr=("rolling_mean", lambda s: s.autocorr(lag=10) if len(s) > 10 else 0),
               ))

    return {"seed": seed, "n_rows": n_rows, "categories": len(summary)}


if __name__ == "__main__":
    results = pmap(
        process_chunk,
        range(60),
        n_jobs=8,
        show_job_bars=True,
        desc="Processing",
    )
    print(f"\nDone! Processed {sum(r['n_rows'] for r in results):,} total rows across {len(results)} chunks.")
