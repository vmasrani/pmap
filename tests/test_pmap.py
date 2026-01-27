#!/usr/bin/env -S uv run --script
"""Comprehensive pmap test — covers both backends, all execution modes, and edge cases."""
import time
import warnings
from loguru import logger
import rich
from pmap import pmap

ITEMS = range(5)
EXPECTED = [0, 2, 4, 6, 8]


def worker(i: int) -> int:
    """Worker with all output methods: print, rich.print, loguru."""
    print(f"print: item {i}")
    rich.print(f"[bold cyan]rich: item {i}[/bold cyan]")
    logger.info(f"loguru: item {i}")
    time.sleep(0.1)
    return i * 2


def worker_with_warnings(i: int) -> int:
    """Worker that emits warnings."""
    if i % 2 == 0:
        warnings.warn(f"Warning for item {i}", UserWarning)
    time.sleep(0.01)
    return i * 2


def worker_that_fails(i: int) -> int:
    """Worker that raises on odd inputs."""
    if i % 2 == 1:
        raise ValueError(f"Item {i} is odd")
    return i * 2


def run_test(name: str, fn=worker, items=ITEMS, expected=EXPECTED, **kwargs):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"kwargs: {kwargs}")
    print(f"{'='*60}")
    results = pmap(fn, items, **kwargs)
    print(f"\nResults: {results}")
    if expected is not None:
        assert results == expected, f"Expected {expected}, got {results}"
    print("PASSED")
    return results


if __name__ == "__main__":
    # ── Rich backend (default in terminal) ──────────────────────
    run_test("Rich: Processes + Simple Bar", n_jobs=2, backend='rich')
    run_test("Rich: Processes + Job Bars", n_jobs=2, show_job_bars=True, backend='rich')
    run_test("Rich: Threads + Simple Bar", n_jobs=2, prefer='threads', backend='rich')
    run_test("Rich: Threads + Job Bars", n_jobs=2, prefer='threads', show_job_bars=True, backend='rich')
    run_test("Rich: Sequential (n_jobs=1)", n_jobs=1, backend='rich')
    run_test("Rich: Disabled Progress", n_jobs=2, disable_tqdm=True, backend='rich')
    run_test("Rich: Job Bars + Disabled Progress", n_jobs=2, show_job_bars=True, disable_tqdm=True, backend='rich')

    # ── tqdm backend ────────────────────────────────────────────
    run_test("tqdm: Processes + Simple Bar", n_jobs=2, backend='tqdm')
    run_test("tqdm: Processes + Job Bars", n_jobs=2, show_job_bars=True, backend='tqdm')
    run_test("tqdm: Threads + Simple Bar", n_jobs=2, prefer='threads', backend='tqdm')
    run_test("tqdm: Threads + Job Bars", n_jobs=2, prefer='threads', show_job_bars=True, backend='tqdm')
    run_test("tqdm: Sequential (n_jobs=1)", n_jobs=1, backend='tqdm')
    run_test("tqdm: Disabled Progress", n_jobs=2, disable_tqdm=True, backend='tqdm')

    # ── Auto backend (should pick rich in terminal) ─────────────
    run_test("Auto: Default backend", n_jobs=2)

    # ── safe_mode ───────────────────────────────────────────────
    results = run_test(
        "safe_mode: Catches errors",
        fn=worker_that_fails, items=range(4), expected=None,
        n_jobs=2, safe_mode=True, backend='rich',
    )
    assert results[0] == 0  # i=0 succeeds
    assert isinstance(results[1], dict) and results[1]['error_type'] == 'ValueError'  # i=1 fails
    assert results[2] == 4  # i=2 succeeds
    assert isinstance(results[3], dict) and results[3]['error_type'] == 'ValueError'  # i=3 fails
    print("safe_mode assertions PASSED")

    results = run_test(
        "safe_mode (tqdm): Catches errors",
        fn=worker_that_fails, items=range(4), expected=None,
        n_jobs=2, safe_mode=True, backend='tqdm',
    )
    assert results[0] == 0
    assert isinstance(results[1], dict) and results[1]['error_type'] == 'ValueError'
    assert results[2] == 4
    assert isinstance(results[3], dict) and results[3]['error_type'] == 'ValueError'
    print("safe_mode (tqdm) assertions PASSED")

    # ── Warnings ────────────────────────────────────────────────
    run_test("Warnings captured", fn=worker_with_warnings, n_jobs=2, backend='rich')

    # ── Batch size ──────────────────────────────────────────────
    run_test("batch_size=1", n_jobs=2, batch_size=1, backend='rich')
    run_test("batch_size=auto", n_jobs=2, batch_size='auto', backend='rich')

    print(f"\n{'='*60}")
    print("ALL TESTS PASSED!")
    print(f"{'='*60}")
