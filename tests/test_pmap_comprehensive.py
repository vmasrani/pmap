#!/usr/bin/env -S uv run --script
"""Comprehensive pytest suite for pmap — correctness, performance, and edge cases.

Run with: uv run pytest tests/test_pmap_comprehensive.py -v
"""
import time
import warnings
from functools import partial

import pandas as pd
import pytest
from loguru import logger

from pmap import pmap, pmap_df, safe


# ── Worker functions ────────────────────────────────────────────

def worker_double(i: int) -> int:
    time.sleep(0.05)
    return i * 2


def worker_fast(i: int) -> int:
    return i * 2


def worker_with_logging(i: int) -> int:
    import rich
    print(f"print: {i}")
    rich.print(f"[cyan]rich: {i}[/cyan]")
    logger.info(f"loguru: {i}")
    time.sleep(0.05)
    return i * 2


def worker_that_fails(i: int) -> int:
    if i % 2 == 1:
        raise ValueError(f"Item {i} is odd")
    return i * 2


def worker_returns_none(i: int):
    time.sleep(0.01)
    return None


def worker_returns_mixed(i: int):
    if i == 0:
        return 42
    elif i == 1:
        return "hello"
    elif i == 2:
        return [1, 2, 3]
    else:
        return {"key": i}


def worker_with_kwargs(i: int, multiplier: int = 1) -> int:
    return i * multiplier


def worker_with_warnings(i: int) -> int:
    if i % 2 == 0:
        warnings.warn(f"Warning for item {i}", UserWarning)
    time.sleep(0.01)
    return i * 2


def worker_slow(i: int) -> int:
    time.sleep(0.1)
    return i * 2


def df_worker(chunk) -> pd.DataFrame:
    # np.array_split converts DataFrames to numpy arrays, losing column names
    if isinstance(chunk, pd.DataFrame):
        df = chunk.copy()
    else:
        df = pd.DataFrame(chunk, columns=["value"])
    df["doubled"] = df["value"] * 2
    return df


# ── Correctness tests (parametrized across backends) ───────────

ITEMS = list(range(50))
EXPECTED = [i * 2 for i in ITEMS]
N_JOBS = 10

BACKEND_PARAMS = [
    pytest.param("rich", id="rich"),
    pytest.param("tqdm", id="tqdm"),
]


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestProcessesSimpleBar:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, backend=backend)
        assert results == EXPECTED

    def test_with_logging(self, backend):
        results = pmap(worker_with_logging, ITEMS, n_jobs=N_JOBS, backend=backend)
        assert results == EXPECTED


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestProcessesJobBars:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, show_job_bars=True, backend=backend)
        assert results == EXPECTED


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestThreadsSimpleBar:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, prefer="threads", backend=backend)
        assert results == EXPECTED


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestThreadsJobBars:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, prefer="threads", show_job_bars=True, backend=backend)
        assert results == EXPECTED


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestSequential:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=1, backend=backend)
        assert results == EXPECTED


@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestDisabledProgress:
    def test_results_correct(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, disable_tqdm=True, backend=backend)
        assert results == EXPECTED

    def test_job_bars_disabled(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, show_job_bars=True, disable_tqdm=True, backend=backend)
        assert results == EXPECTED


# ── safe_mode ───────────────────────────────────────────────────

@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestSafeMode:
    def test_catches_errors(self, backend):
        results = pmap(worker_that_fails, range(6), n_jobs=N_JOBS, safe_mode=True, backend=backend)
        # Even indices succeed, odd indices fail
        assert results[0] == 0
        assert results[2] == 4
        assert results[4] == 8
        assert isinstance(results[1], dict)
        assert results[1]["error_type"] == "ValueError"
        assert isinstance(results[3], dict)
        assert isinstance(results[5], dict)

    def test_safe_decorator_directly(self, backend):
        safe_fn = safe(worker_that_fails)
        assert safe_fn(0) == 0
        result = safe_fn(1)
        assert isinstance(result, dict)
        assert result["error_type"] == "ValueError"


# ── batch_size ──────────────────────────────────────────────────

@pytest.mark.parametrize("backend", BACKEND_PARAMS)
class TestBatchSize:
    def test_batch_size_1(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, batch_size=1, backend=backend)
        assert results == EXPECTED

    def test_batch_size_auto(self, backend):
        results = pmap(worker_double, ITEMS, n_jobs=N_JOBS, batch_size="auto", backend=backend)
        assert results == EXPECTED


# ── Edge cases ──────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_array(self):
        results = pmap(worker_double, [], n_jobs=N_JOBS, backend="rich")
        assert results == []

    def test_single_item(self):
        results = pmap(worker_double, [42], n_jobs=N_JOBS, backend="rich")
        assert results == [84]

    def test_large_array(self):
        items = list(range(500))
        results = pmap(worker_fast, items, n_jobs=N_JOBS, backend="rich")
        assert results == [i * 2 for i in items]

    def test_returns_none(self):
        results = pmap(worker_returns_none, range(5), n_jobs=N_JOBS, backend="rich")
        assert results == [None] * 5

    def test_returns_mixed_types(self):
        results = pmap(worker_returns_mixed, range(4), n_jobs=N_JOBS, backend="rich")
        assert results[0] == 42
        assert results[1] == "hello"
        assert results[2] == [1, 2, 3]
        assert results[3] == {"key": 3}

    def test_very_fast_workers(self):
        results = pmap(worker_fast, range(200), n_jobs=N_JOBS, backend="rich")
        assert results == [i * 2 for i in range(200)]

    def test_partial_kwargs(self):
        fn = partial(worker_with_kwargs, multiplier=3)
        results = pmap(fn, range(5), n_jobs=N_JOBS, backend="rich")
        assert results == [0, 3, 6, 9, 12]

    def test_generator_input(self):
        results = pmap(worker_fast, iter(range(10)), n_jobs=N_JOBS, backend="rich")
        assert results == [i * 2 for i in range(10)]

    def test_warnings_captured(self):
        results = pmap(worker_with_warnings, ITEMS, n_jobs=N_JOBS, backend="rich")
        assert results == EXPECTED

    def test_auto_backend_in_terminal(self):
        results = pmap(worker_fast, ITEMS, n_jobs=N_JOBS, backend="auto")
        assert results == EXPECTED

    def test_custom_desc(self):
        results = pmap(worker_fast, ITEMS, n_jobs=N_JOBS, desc="Custom", backend="rich")
        assert results == EXPECTED


# ── pmap_df ─────────────────────────────────────────────────────

class TestPmapDf:
    def test_basic(self):
        df = pd.DataFrame({"value": range(1000)})
        result = pmap_df(df_worker, df, n_chunks=20, n_jobs=10, prefer="threads", backend="rich")
        assert len(result) == 1000
        assert "doubled" in result.columns
        assert list(result["doubled"]) == [i * 2 for i in range(1000)]

    def test_with_groups(self):
        df = pd.DataFrame({
            "value": range(1000),
            "group": [i % 10 for i in range(1000)],
        })
        result = pmap_df(df_worker, df, n_chunks=10, groups="group", n_jobs=10, prefer="threads", backend="rich")
        assert len(result) == 1000
        assert "doubled" in result.columns


# ── Performance tests ───────────────────────────────────────────

class TestPerformance:
    def test_parallel_faster_than_sequential(self):
        items = list(range(50))

        start = time.perf_counter()
        pmap(worker_slow, items, n_jobs=1, backend="rich", disable_tqdm=True)
        sequential_time = time.perf_counter() - start

        start = time.perf_counter()
        pmap(worker_slow, items, n_jobs=N_JOBS, backend="rich", disable_tqdm=True)
        parallel_time = time.perf_counter() - start

        speedup = sequential_time / parallel_time
        assert speedup > 1.5, f"Expected >1.5x speedup, got {speedup:.1f}x"

    def test_wall_clock_reasonable(self):
        items = list(range(50))
        start = time.perf_counter()
        pmap(worker_slow, items, n_jobs=N_JOBS, backend="rich", disable_tqdm=True)
        elapsed = time.perf_counter() - start
        # 50 items * 0.1s / 10 jobs = 0.5s theoretical, allow up to 3.0s for overhead
        assert elapsed < 3.0, f"Expected <3.0s, took {elapsed:.2f}s"

    def test_overhead_acceptable(self):
        """pmap overhead vs raw joblib should be small."""
        from joblib import Parallel, delayed
        items = list(range(100))

        start = time.perf_counter()
        Parallel(n_jobs=N_JOBS)(delayed(worker_fast)(i) for i in items)
        raw_time = time.perf_counter() - start

        start = time.perf_counter()
        pmap(worker_fast, items, n_jobs=N_JOBS, backend="rich", disable_tqdm=True)
        pmap_time = time.perf_counter() - start

        overhead = pmap_time - raw_time
        assert overhead < 1.0, f"pmap overhead {overhead:.2f}s exceeds 1.0s"
