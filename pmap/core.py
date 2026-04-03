"""Shared core for pmap — dataclasses, orchestration, and joblib utilities.

Used by both the Rich and tqdm backends to avoid duplication.
"""
from __future__ import annotations

import contextlib
import multiprocessing
import queue
from dataclasses import dataclass, field
from typing import Any, Callable

import joblib

from .loguru_routing import (
    LoguruConfig,
    find_loguru_names,
    strip_loguru_from_globals,
    reinject_loguru,
    make_worker_wrapper,
    make_signaling_wrapper,
)


@dataclass
class ParallelMode:
    """Configuration for parallel execution mode."""
    using_threads: bool
    log_queue: Any  # multiprocessing.Queue | None
    wrapped_func: Callable
    stripped_names: set[str]
    manager: Any = None  # multiprocessing.Manager | None
    job_queue: Any = None  # Queue for worker start/done signals


def prepare_parallel_mode(f: Callable, prefer: str | None, show_job_bars: bool = False) -> ParallelMode:
    """Prepare function and logging for the selected parallel backend."""
    if prefer == 'threads':
        job_queue = queue.Queue() if show_job_bars else None
        wrapped = make_signaling_wrapper(f, job_queue) if job_queue else f
        return ParallelMode(
            using_threads=True,
            log_queue=None,
            wrapped_func=wrapped,
            stripped_names=set(),
            job_queue=job_queue,
        )

    stripped_names = find_loguru_names(f)
    strip_loguru_from_globals(f, stripped_names)
    manager = multiprocessing.Manager()
    log_queue = manager.Queue()
    job_queue = manager.Queue() if show_job_bars else None
    config = LoguruConfig(stripped_names, log_queue)

    wrapped = make_worker_wrapper(f, config, job_queue=job_queue)

    return ParallelMode(
        using_threads=False,
        log_queue=log_queue,
        wrapped_func=wrapped,
        stripped_names=stripped_names,
        manager=manager,
        job_queue=job_queue,
    )


@contextlib.contextmanager
def joblib_callback_patch(callback_class):
    """Temporarily replace joblib's BatchCompletionCallBack with a custom class."""
    old = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = callback_class
    try:
        yield
    finally:
        joblib.parallel.BatchCompletionCallBack = old


def run_pmap(
    f: Callable,
    arr,
    n_jobs: int,
    disable_tqdm: bool,
    spawn: bool,
    batch_size,
    show_job_bars: bool,
    safe_mode: bool,
    safe_fn: Callable,
    sequential_map_fn: Callable,
    run_simple_fn: Callable,
    run_job_bars_fn: Callable,
    **kwargs,
) -> list:
    """Shared orchestration for both Rich and tqdm backends."""
    arr = list(arr)
    desc = kwargs.pop('desc', 'Processing')
    total_tasks = len(arr)

    if spawn:
        multiprocessing.set_start_method('spawn', force=True)

    f = safe_fn(f) if safe_mode else f

    if n_jobs == 1:
        return sequential_map_fn(f, arr, desc, disable_tqdm)

    mode = prepare_parallel_mode(f, kwargs.get('prefer'), show_job_bars=show_job_bars)

    actual_n_jobs = n_jobs if n_jobs != -1 else multiprocessing.cpu_count()
    total_cpus = min(actual_n_jobs, total_tasks)

    try:
        if show_job_bars:
            results = run_job_bars_fn(
                mode, arr, n_jobs, batch_size, disable_tqdm, desc,
                total_tasks, total_cpus, kwargs
            )
        else:
            results = run_simple_fn(
                mode, arr, n_jobs, batch_size, disable_tqdm, desc, kwargs
            )
    finally:
        if mode.stripped_names:
            reinject_loguru(f, mode.stripped_names)
        if mode.manager is not None:
            mode.manager.shutdown()

    return results
