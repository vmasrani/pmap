#!/usr/bin/env -S uv run --script
"""Demo: batch_size=1 dispatches items one at a time for fine-grained progress."""
import time
from pmap import pmap


def process(x):
    time.sleep(1.6)
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(20), n_jobs=4, batch_size=1, desc="Batch size=1", backend="rich")
    print(f"\nDone! {len(results)} items processed with batch_size=1.")
