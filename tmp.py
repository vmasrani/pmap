#!/usr/bin/env -S uv run --script
"""Test script: 100 jobs each lasting 8-30 seconds."""

import random
import time
from pmap import pmap


def slow_task(i):
    duration = random.uniform(3, 5)
    time.sleep(duration)
    return i


if __name__ == "__main__":
    results = pmap(slow_task, list(range(100)), show_job_bars=True)
    print(f"Done: {len(results)} results")
