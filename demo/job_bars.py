#!/usr/bin/env -S uv run --script
"""Demo: per-job progress bars with CPU panel."""
import time
from pmap import pmap


def process(x):
    time.sleep(2.4 + (x % 3) * 0.2)
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(20), n_jobs=10, show_job_bars=True, desc="Training", backend="rich")
    print(f"\nDone! {len(results)} items processed.")
