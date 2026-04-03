#!/usr/bin/env -S uv run --script
"""Demo: thread-based parallelism (prefer='threads')."""
import time
from pmap import pmap


def process(x):
    time.sleep(1.6)
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(20), n_jobs=4, prefer="threads", desc="Threading", backend="rich")
    print(f"\nDone! {len(results)} items processed with threads.")
