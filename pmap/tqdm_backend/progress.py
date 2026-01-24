"""Unified tqdm-based progress bars - single implementation for terminal and notebook."""
from __future__ import annotations

import contextlib
import multiprocessing
import re
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable
import queue as queue_module

import joblib
from joblib import Parallel, delayed
from tqdm.auto import tqdm

# ANSI escape code pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


from .. import is_notebook


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub('', text)


def safe_write(pbar, message: str) -> None:
    """Write message compatible with both terminal and notebook."""
    if is_notebook():
        # In notebook: use print() - logs appear above, widget stays at bottom
        print(strip_ansi(message))
    else:
        # In terminal: use tqdm.write() for proper cursor handling
        pbar.write(message)

from ..loguru_routing import (
    LoguruConfig,
    find_loguru_names,
    strip_loguru_from_globals,
    make_worker_wrapper,
)


@dataclass
class ParallelMode:
    """Configuration for parallel execution."""
    using_threads: bool
    log_queue: Any  # multiprocessing.Queue | None
    wrapped_func: Callable
    stripped_names: set[str]
    manager: Any = None  # multiprocessing.Manager | None


def prepare_parallel_mode(f: Callable, prefer: str | None) -> ParallelMode:
    """Prepare function for parallel execution."""
    using_threads = prefer == 'threads'

    if using_threads:
        return ParallelMode(
            using_threads=True,
            log_queue=None,
            wrapped_func=f,
            stripped_names=set(),
        )

    # Process mode: need Manager for pickleable queue
    stripped_names = find_loguru_names(f)
    strip_loguru_from_globals(f, stripped_names)
    manager = multiprocessing.Manager()
    log_queue = manager.Queue()
    config = LoguruConfig(stripped_names, log_queue)

    return ParallelMode(
        using_threads=False,
        log_queue=log_queue,
        wrapped_func=make_worker_wrapper(f, config),
        stripped_names=stripped_names,
        manager=manager,
    )


def sequential_map(f: Callable, arr: list, desc: str, disable: bool) -> list:
    """Sequential map with tqdm progress bar."""
    if disable:
        return [f(item) for item in arr]

    results = []
    with redirect_loguru_to_tqdm() as pbar_ref:
        pbar = tqdm(arr, desc=desc)
        pbar_ref[0] = pbar
        for item in pbar:
            results.append(f(item))
    return results


@contextlib.contextmanager
def redirect_loguru_to_tqdm():
    """Redirect loguru output to tqdm.write()."""
    pbar_ref = [None]  # Mutable reference for pbar
    in_notebook = is_notebook()

    def write_fn(m):
        msg = str(m).rstrip()
        if pbar_ref[0] is not None:
            safe_write(pbar_ref[0], msg)
        else:
            print(strip_ansi(msg) if in_notebook else msg)

    try:
        import loguru
        loguru.logger.remove()
        handler_id = loguru.logger.add(
            write_fn,
            colorize=not in_notebook,  # No colors in notebook
            format="{time:HH:mm:ss} | {level: <8} | {message}"
        )
        try:
            yield pbar_ref
        finally:
            loguru.logger.remove(handler_id)
            loguru.logger.add(sys.stderr)
    except ImportError:
        yield pbar_ref


@contextlib.contextmanager
def log_consumer_tqdm(log_queue: Any, pbar):
    """Consume log messages from queue and write via tqdm."""
    if log_queue is None:
        yield
        return

    stop_event = threading.Event()

    def consumer():
        while not stop_event.is_set():
            try:
                message = log_queue.get(timeout=0.1)
                if message and pbar:
                    safe_write(pbar, message)
            except queue_module.Empty:
                continue
        # Drain remaining
        while True:
            try:
                message = log_queue.get_nowait()
                if message and pbar:
                    safe_write(pbar, message)
            except queue_module.Empty:
                break

    thread = threading.Thread(target=consumer, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)


def run_with_simple_bar(mode: ParallelMode, arr: list, n_jobs: int, batch_size,
                        disable_tqdm: bool, desc: str, kwargs: dict) -> list:
    """Run with single tqdm progress bar."""
    pbar = tqdm(total=len(arr), desc=desc, disable=disable_tqdm)

    class TqdmCallback(joblib.parallel.BatchCompletionCallBack):
        def __call__(self, out):
            pbar.update(n=self.batch_size)
            return super().__call__(out)

    old_cb = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = TqdmCallback

    try:
        with log_consumer_tqdm(mode.log_queue, pbar):
            if mode.using_threads:
                with redirect_loguru_to_tqdm() as pbar_ref:
                    pbar_ref[0] = pbar
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        delayed(mode.wrapped_func)(i) for i in arr
                    )
            else:
                results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                    delayed(mode.wrapped_func)(i) for i in arr
                )
    finally:
        joblib.parallel.BatchCompletionCallBack = old_cb
        pbar.close()

    return results


def run_with_job_bars(mode: ParallelMode, arr: list, n_jobs: int, batch_size,
                      disable_tqdm: bool, desc: str, total_tasks: int,
                      total_cpus: int, kwargs: dict) -> list:
    """Run with per-job tqdm progress bars."""
    # In notebooks, multi-position bars don't work well - use simple bar
    if is_notebook():
        return run_with_simple_bar(mode, arr, n_jobs, batch_size,
                                   disable_tqdm, desc, kwargs)

    # Overall progress bar at position 0
    overall = tqdm(total=total_tasks, desc=f"{desc}", position=0,
                   disable=disable_tqdm, leave=True)

    # Track active job bars
    active_bars = {}
    bar_lock = threading.Lock()
    job_counter = [0]

    class TqdmJobCallback(joblib.parallel.BatchCompletionCallBack):
        def __call__(self, out):
            with bar_lock:
                overall.update(n=self.batch_size)
                job_counter[0] += 1
                job_num = job_counter[0]

                # Clean up old bars (keep max total_cpus active)
                while len(active_bars) >= total_cpus:
                    oldest = min(active_bars.keys())
                    active_bars[oldest].close()
                    del active_bars[oldest]

                # Add new bar showing job completion
                pos = (len(active_bars) % total_cpus) + 1
                bar = tqdm(total=1, desc=f"  Job {job_num:>4}", position=pos,
                          leave=False, disable=disable_tqdm,
                          bar_format='{desc}: {bar} | {elapsed}')
                bar.update(1)
                active_bars[job_num] = bar

            return super().__call__(out)

    old_cb = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = TqdmJobCallback

    try:
        with log_consumer_tqdm(mode.log_queue, overall):
            if mode.using_threads:
                with redirect_loguru_to_tqdm() as pbar_ref:
                    pbar_ref[0] = overall
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        delayed(mode.wrapped_func)(i) for i in arr
                    )
            else:
                results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                    delayed(mode.wrapped_func)(i) for i in arr
                )
    finally:
        joblib.parallel.BatchCompletionCallBack = old_cb
        with bar_lock:
            for bar in active_bars.values():
                bar.close()
        overall.close()
        # Clear the extra lines from job bars
        print('\n' * total_cpus, end='')

    return results
