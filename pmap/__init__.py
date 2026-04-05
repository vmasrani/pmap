"""Parallel map with progress bars.

Usage:
    from pmap import pmap

    results = pmap(fn, items)  # Simple progress bar
    results = pmap(fn, items, show_job_bars=True)  # Per-job progress bars
    results = pmap(fn, items, backend='tqdm')  # Force tqdm backend
"""
from __future__ import annotations

import time
import warnings
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import pandas as pd

from .core import run_pmap
from .progress_bars import (
    sequential_map,
    run_with_simple_bar,
    run_with_job_bars,
)

__all__ = ['pmap', 'pmap_df', 'run_async', 'safe', 'is_notebook']


def is_notebook() -> bool:
    """Detect if running in Jupyter notebook."""
    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        return shell == 'ZMQInteractiveShell'
    except NameError:
        return False

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="'DataFrame.swapaxes' is deprecated.*"
)


def safe(f: Callable) -> Callable:
    """Wrap function to catch exceptions and return error dict instead of raising."""
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return {
                'error': str(e),
                'error_type': type(e).__name__,
                'args': args,
                'kwargs': kwargs
            }
    return wrapper


def pmap(f, arr, n_jobs=-1, disable_tqdm=False, safe_mode=False, spawn=False, batch_size='auto', show_job_bars=False, backend='auto', **kwargs):
    """Parallel map with progress bar.

    Args:
        f: Function to apply to each element
        arr: Iterable of elements to process
        n_jobs: Number of parallel jobs (-1 for all CPUs)
        disable_tqdm: Disable progress bar
        safe_mode: Catch exceptions and return error dicts instead of raising
        spawn: Use spawn multiprocessing start method
        batch_size: Joblib batch size ('auto' or int). Forced to 1 when
            show_job_bars=True to ensure all workers are visible.
        show_job_bars: Show per-job progress bars with CPU info (default: False)
        backend: 'auto' (default), 'rich', or 'tqdm'
                 'auto' uses tqdm in notebooks (Rich doesn't support notebooks)
        **kwargs: Additional arguments passed to joblib.Parallel
            - desc: Description for progress bar (default: 'Processing')
            - prefer: 'threads' for threading backend

    Returns:
        List of results from applying f to each element in arr

    Note:
        - In process mode, all output (print, rich.print, loguru) is routed through
          loguru and appears above the progress bar in real-time
        - In thread mode, output goes directly to stdout (shared between threads)
    """
    if backend == 'auto':
        backend = 'tqdm' if is_notebook() else 'rich'

    if backend == 'tqdm':
        from .tqdm_backend import pmap as tqdm_pmap
        return tqdm_pmap(f, arr, n_jobs=n_jobs, disable_tqdm=disable_tqdm,
                         safe_mode=safe_mode, spawn=spawn, batch_size=batch_size,
                         show_job_bars=show_job_bars, **kwargs)

    return run_pmap(
        f, arr, n_jobs=n_jobs, disable_tqdm=disable_tqdm, spawn=spawn,
        batch_size=batch_size, show_job_bars=show_job_bars,
        safe_mode=safe_mode,
        safe_fn=safe, sequential_map_fn=sequential_map,
        run_simple_fn=run_with_simple_bar, run_job_bars_fn=run_with_job_bars,
        **kwargs,
    )


def pmap_df(
    f: Callable,
    df: "pd.DataFrame",
    n_chunks: int = 100,
    groups: str | None = None,
    axis: int = 0,
    safe_mode: bool = False,
    **kwargs,
) -> "pd.DataFrame":
    """Parallel map over DataFrame chunks.

    See: https://towardsdatascience.com/make-your-own-super-pandas-using-multiproc-1c04f41944a1
    """
    import numpy as np
    import pandas as pd
    from sklearn.model_selection import GroupKFold

    if groups:
        n_chunks = min(n_chunks, df[groups].nunique())
        group_kfold = GroupKFold(n_splits=n_chunks)
        df_split = [df.iloc[test_index] for _, test_index in group_kfold.split(df, groups=df[groups])]
    else:
        df_split = np.array_split(df, n_chunks)
    df = pd.concat(pmap(f, df_split, safe_mode=safe_mode, **kwargs), axis=axis)
    return df


def run_async(func):
    """Run function asynchronously and return a queue for retrieving results."""
    import multiprocessing

    def func_with_queue(queue, *args, **kwargs):
        print(f'Running function {func.__name__}{args} {kwargs} ... ')
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        queue.put(result)
        print(f'Function {func.__name__}{args} {kwargs} Took {total_time:.4f} seconds')

    def wrapper(*args, **kwargs):
        queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=func_with_queue, args=(queue, *args), kwargs=kwargs)
        process.start()
        return queue
    return wrapper
