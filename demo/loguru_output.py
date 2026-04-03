#!/usr/bin/env -S uv run --script
"""Demo: loguru/print output routed above progress bars."""
import time
from loguru import logger
from pmap import pmap


def process(x):
    logger.info(f"Processing item {x}")
    time.sleep(2.1)
    if x % 5 == 0:
        logger.warning(f"Item {x} took extra time")
    return x ** 2


if __name__ == "__main__":
    results = pmap(process, range(15), n_jobs=4, desc="Analyzing", backend="rich")
    print(f"\nDone! {len(results)} items processed.")
