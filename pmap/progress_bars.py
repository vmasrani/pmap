"""Rich progress bar implementations for parallel execution."""
from __future__ import annotations

import contextlib
import itertools
import threading
import time
from typing import Callable

import joblib
from joblib import Parallel, delayed
from rich.live import Live
from rich.progress import (
    Progress,
    BarColumn,
    MofNCompleteColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from .core import ParallelMode, joblib_callback_patch
from .loguru_routing import redirect_loguru_to_live, log_consumer
from .progress_styles import (
    create_progress_columns,
    create_progress_table,
    make_job_description,
)

# Progress bar refresh rate (Hz)
REFRESH_RATE = 16

# Thread polling interval for progress updates (seconds)
PROGRESS_POLL_INTERVAL = 0.1


@contextlib.contextmanager
def progress_with_live(desc: str, total: int, disable: bool = False):
    """Progress bar with Live display that allows printing above it."""
    if disable:
        yield None, None
        return

    progress = Progress(
        TextColumn("[progress.percentage]{task.description} {task.percentage:>3.0f}%"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    )
    task_id = progress.add_task(desc, total=total)

    with Live(progress, refresh_per_second=REFRESH_RATE, transient=False) as live:

        class Callback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, out):
                progress.update(task_id, advance=self.batch_size)
                live.refresh()
                return super().__call__(out)

        with joblib_callback_patch(Callback):
            try:
                yield progress, live
            finally:
                progress.update(task_id, completed=total)


def sequential_map(f: Callable, arr: list, desc: str, disable: bool) -> list:
    """Sequential map with progress bar for n_jobs=1 case."""
    if disable:
        return [f(item) for item in arr]

    results = []
    progress = Progress(
        TextColumn("[progress.percentage]{task.description} {task.percentage:>3.0f}%"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    )
    task_id = progress.add_task(desc, total=len(arr))

    with Live(progress, refresh_per_second=16, transient=False) as live:
        with redirect_loguru_to_live(live):
            for item in arr:
                results.append(f(item))
                progress.update(task_id, advance=1)
    return results


def run_with_simple_bar(mode: ParallelMode, arr: list, n_jobs: int, batch_size, disable_tqdm: bool, desc: str, kwargs: dict) -> list:
    """Run parallel execution with a simple single progress bar."""
    with progress_with_live(desc, total=len(arr), disable=disable_tqdm) as (progress, live):
        with log_consumer(mode.log_queue, live):
            if mode.using_threads:
                with redirect_loguru_to_live(live):
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        delayed(mode.wrapped_func)(i) for i in arr
                    )
            else:
                results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                    delayed(mode.wrapped_func)(i) for i in arr
                )
    return results


def run_with_job_bars(mode: ParallelMode, arr: list, n_jobs: int, batch_size, disable_tqdm: bool, desc: str, total_tasks: int, total_cpus: int, kwargs: dict) -> list:
    """Run parallel execution with per-job progress bars and CPU info."""
    job_progress, overall_progress = create_progress_columns(disable_tqdm)

    task_id = job_progress.add_task(desc, total=total_tasks)
    overall_task_id = overall_progress.add_task(
        str(Text.assemble(("", "dim blue"), (" Total", "bold white"))),
        total=total_tasks
    )

    class DynamicProgressTable:
        def __rich__(self):
            completed = int(job_progress.tasks[task_id].completed)
            return create_progress_table(
                job_progress, overall_progress, total_cpus, completed, total_tasks
            )

    with contextlib.ExitStack() as stack:
        live = stack.enter_context(Live(DynamicProgressTable(), refresh_per_second=REFRESH_RATE, transient=False))
        if mode.log_queue:
            stack.enter_context(log_consumer(mode.log_queue, live))
        stack.enter_context(
            _job_bars_callback(job_progress, overall_progress, task_id, overall_task_id, total_cpus)
        )
        if mode.using_threads:
            stack.enter_context(redirect_loguru_to_live(live))
        results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
            delayed(mode.wrapped_func)(i) for i in arr
        )

    return results


class _JobTimeEstimator:
    """Exponential moving average of per-item job times."""

    def __init__(self, alpha: float = 0.3):
        self._alpha = alpha
        self.avg: float | None = None

    def record(self, elapsed: float, batch_size: int):
        batch_avg = elapsed / batch_size
        if self.avg is None:
            self.avg = batch_avg
        else:
            self.avg = self._alpha * batch_avg + (1 - self._alpha) * self.avg


def _start_estimation_thread(
    job_progress, active_jobs: dict, estimator: _JobTimeEstimator, lock: threading.Lock
) -> tuple[threading.Event, threading.Thread]:
    """Single daemon thread that updates per-job progress bars based on estimated time."""
    stop = threading.Event()

    def run():
        while not stop.is_set():
            if estimator.avg:
                now = time.time()
                with lock:
                    for job_task_id, start_time, _ in list(active_jobs.values()):
                        elapsed = now - start_time
                        pct = min(99, int(100 * elapsed / estimator.avg))
                        job_progress.update(job_task_id, completed=pct)
            time.sleep(PROGRESS_POLL_INTERVAL)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


@contextlib.contextmanager
def _job_bars_callback(job_progress, overall_progress, overall_job_task_id, overall_progress_task_id, total_cpus):
    """Monkeypatch joblib callback for per-job progress bars with time estimation."""
    estimator = _JobTimeEstimator()
    active_jobs: dict[int, tuple] = {}  # job_idx -> (task_id, start_time, job_number)
    lock = threading.Lock()
    job_counter = itertools.count(1)
    batch_start_time = [time.time()]
    completed_jobs = [0]

    stop, thread = _start_estimation_thread(job_progress, active_jobs, estimator, lock)

    class Callback(joblib.parallel.BatchCompletionCallBack):
        def __call__(self, *args, **kwargs):
            now = time.time()

            if self.batch_size > 0:
                estimator.record(now - batch_start_time[0], self.batch_size)
                batch_start_time[0] = now

            with lock:
                # Keep at most total_cpus bars visible
                while len(active_jobs) >= total_cpus:
                    oldest = min(active_jobs)
                    job_progress.remove_task(active_jobs.pop(oldest)[0])

                job_number = next(job_counter)
                new_task_id = job_progress.add_task(
                    make_job_description(job_number),
                    total=100, completed=0,
                )
                active_jobs[completed_jobs[0]] = (new_task_id, now, job_number)

            job_progress.update(overall_job_task_id, advance=self.batch_size)
            overall_progress.update(overall_progress_task_id, advance=self.batch_size)
            completed_jobs[0] += self.batch_size

            return super().__call__(*args, **kwargs)

    with joblib_callback_patch(Callback):
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=1.0)
            job_progress.update(overall_job_task_id, completed=job_progress.tasks[overall_job_task_id].total)
            overall_progress.update(overall_progress_task_id, completed=overall_progress.tasks[overall_progress_task_id].total)
