"""Unified tqdm-based pmap - works in terminals and notebooks."""
from __future__ import annotations

import multiprocessing

from .. import safe
from ..loguru_routing import reinject_loguru
from .progress import (
    prepare_parallel_mode,
    sequential_map,
    run_with_simple_bar,
    run_with_job_bars,
)

__all__ = ['pmap', 'safe']


def pmap(f, arr, n_jobs=-1, disable_tqdm=False, safe_mode=False, spawn=False,
         batch_size='auto', show_job_bars=False, **kwargs):
    """Parallel map with tqdm progress bar (works in terminals and notebooks).

    Args:
        f: Function to apply to each element
        arr: Iterable of elements to process
        n_jobs: Number of parallel jobs (-1 for all CPUs)
        disable_tqdm: Disable progress bar
        safe_mode: Catch exceptions and return error dicts
        spawn: Use spawn multiprocessing start method
        batch_size: Joblib batch size ('auto' or int)
        show_job_bars: Show per-job progress bars
        **kwargs: Additional arguments passed to joblib.Parallel
            - desc: Description for progress bar (default: 'Processing')
            - prefer: 'threads' for threading backend
    """
    arr = list(arr)
    desc = kwargs.pop('desc', 'Processing')
    total_tasks = len(arr)

    if spawn:
        multiprocessing.set_start_method('spawn', force=True)

    f = safe(f) if safe_mode else f

    if n_jobs == 1:
        return sequential_map(f, arr, desc, disable_tqdm)

    mode = prepare_parallel_mode(f, kwargs.get('prefer'))

    actual_n_jobs = n_jobs if n_jobs != -1 else multiprocessing.cpu_count()
    total_cpus = min(actual_n_jobs, total_tasks)

    try:
        if show_job_bars:
            results = run_with_job_bars(
                mode, arr, n_jobs, batch_size, disable_tqdm, desc,
                total_tasks, total_cpus, kwargs
            )
        else:
            results = run_with_simple_bar(
                mode, arr, n_jobs, batch_size, disable_tqdm, desc, kwargs
            )
    finally:
        if mode.stripped_names:
            reinject_loguru(f, mode.stripped_names)
        if mode.manager is not None:
            mode.manager.shutdown()

    return results
