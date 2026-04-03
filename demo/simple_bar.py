#!/usr/bin/env -S uv run --script
"""Demo: simple progress bar."""
import time
from pmap import pmap


def process(x):
    time.sleep(1.6)
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(20), n_jobs=4, desc="Processing", backend="rich")
    print(f"\nDone! {len(results)} items processed.")
