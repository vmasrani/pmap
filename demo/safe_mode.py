#!/usr/bin/env -S uv run --script
"""Demo: safe_mode catches exceptions and returns error dicts instead of crashing."""
import time
from pmap import pmap


def process(x):
    time.sleep(1.6)
    if x % 4 == 3:
        raise ValueError(f"Item {x} failed!")
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(20), n_jobs=4, safe_mode=True, desc="Safe mode", backend="rich")
    successes = [r for r in results if not isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, dict)]
    print(f"\nDone! {len(successes)} succeeded, {len(failures)} caught errors:")
    for f in failures:
        print(f"  - {f['error_type']}: {f['error']}")
