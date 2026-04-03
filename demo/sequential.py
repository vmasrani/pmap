#!/usr/bin/env -S uv run --script
"""Demo: sequential mode (n_jobs=1) — no parallelism, useful for debugging."""
import time
from pmap import pmap


def process(x):
    time.sleep(0.67)
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(12), n_jobs=1, desc="Sequential", backend="rich")
    print(f"\nDone! {len(results)} items processed sequentially.")
