"""Rich progress bar implementations for parallel execution."""
from __future__ import annotations

import contextlib
import math
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


def run_with_job_bars(mode: ParallelMode, arr: list, n_jobs: int, batch_size, disable_tqdm: bool, desc: str, total_tasks: int, total_cpus: int, kwargs: dict, job_bar_style: str = 'pulse') -> list:
    """Run parallel execution with per-job progress bars and CPU info."""
    job_progress = create_progress_columns(disable_tqdm)

    task_id = job_progress.add_task(desc, total=total_tasks)

    class DynamicProgressTable:
        def __rich__(self):
            completed = int(job_progress.tasks[task_id].completed)
            return create_progress_table(
                job_progress, total_cpus, completed, total_tasks
            )

    with contextlib.ExitStack() as stack:
        live = stack.enter_context(Live(DynamicProgressTable(), refresh_per_second=REFRESH_RATE, transient=False))
        if mode.log_queue:
            stack.enter_context(log_consumer(mode.log_queue, live))
        stack.enter_context(
            _job_bars_callback(job_progress, task_id, total_cpus, mode.job_queue, job_bar_style=job_bar_style)
        )
        if mode.using_threads:
            stack.enter_context(redirect_loguru_to_live(live))

        if mode.job_queue:
            results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                delayed(mode.wrapped_func)(idx, item) for idx, item in enumerate(arr)
            )
        else:
            results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                delayed(mode.wrapped_func)(i) for i in arr
            )

    return results


class _JobTimeEstimator:
    """Track per-item job times with EMA and max for conservative estimation."""

    def __init__(self, alpha: float = 0.3):
        self._alpha = alpha
        self.avg: float | None = None
        self.max_time: float = 0.0

    @property
    def reference(self) -> float | None:
        """Conservative reference duration: max of EMA and 80% of longest observed job."""
        return None if self.avg is None else max(self.avg, self.max_time * 0.8)

    def record(self, elapsed: float, batch_size: int):
        batch_avg = elapsed / batch_size
        self.max_time = max(self.max_time, elapsed)
        if self.avg is None:
            self.avg = batch_avg
        else:
            self.avg = self._alpha * batch_avg + (1 - self._alpha) * self.avg


def _dampened_progress(elapsed: float, reference: float) -> int:
    """Dampened fill curve: linear to 70%, then asymptotic approach to 99%."""
    ratio = elapsed / reference
    if ratio < 0.7:
        return int(ratio * 100)
    return min(99, int(70 + 29 * (1 - math.exp(-3 * (ratio - 0.7)))))


def _start_estimation_thread(
    job_progress, active_jobs: dict, estimator: _JobTimeEstimator, lock: threading.Lock
) -> tuple[threading.Event, threading.Thread]:
    """Single daemon thread that updates per-job progress bars based on estimated time."""
    stop = threading.Event()

    def run():
        while not stop.is_set():
            ref = estimator.reference
            if ref:
                now = time.time()
                with lock:
                    for job_task_id, start_time in list(active_jobs.values()):
                        elapsed = now - start_time
                        pct = _dampened_progress(elapsed, ref)
                        job_progress.update(job_task_id, completed=pct)
            time.sleep(PROGRESS_POLL_INTERVAL)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


def _start_signal_monitor(
    job_queue, job_progress, overall_task_id,
    active_jobs: dict, lock: threading.Lock,
    job_bar_style: str = 'pulse',
    estimator: _JobTimeEstimator | None = None,
) -> tuple[threading.Event, threading.Thread]:
    """Monitor thread that reacts to worker start/done signals to manage per-job bars."""
    stop = threading.Event()
    use_pulse = job_bar_style == 'pulse'
    import queue as queue_module

    def run():
        while not stop.is_set():
            try:
                signal, item_idx = job_queue.get(timeout=0.05)
            except (queue_module.Empty, OSError):
                continue

            now = time.time()
            if signal == "start":
                if use_pulse:
                    task_id = job_progress.add_task(
                        make_job_description(item_idx + 1), total=None,
                    )
                else:
                    task_id = job_progress.add_task(
                        make_job_description(item_idx + 1), total=100, completed=0,
                    )
                with lock:
                    active_jobs[item_idx] = (task_id, now)
            elif signal == "done":
                with lock:
                    entry = active_jobs.pop(item_idx, None)
                if entry:
                    task_id, start_time = entry
                    elapsed = now - start_time
                    if estimator:
                        estimator.record(elapsed, 1)
                    if not use_pulse:
                        job_progress.update(task_id, completed=100)
                    job_progress.remove_task(task_id)
                job_progress.update(overall_task_id, advance=1)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


@contextlib.contextmanager
def _job_bars_callback(job_progress, overall_task_id, total_cpus, job_queue=None, job_bar_style='pulse'):
    """Manage per-job progress bars via worker signals (or batch callback fallback)."""
    active_jobs: dict[int, tuple] = {}  # item_idx -> (task_id, start_time)
    lock = threading.Lock()
    use_estimation = job_bar_style == 'estimate'

    estimator = _JobTimeEstimator() if use_estimation else None
    if use_estimation and estimator is not None:
        stop_est, est_thread = _start_estimation_thread(job_progress, active_jobs, estimator, lock)

    if job_queue is not None:
        # Signal-driven mode: monitor thread handles per-job bars
        stop_mon, mon_thread = _start_signal_monitor(
            job_queue, job_progress, overall_task_id,
            active_jobs, lock,
            job_bar_style=job_bar_style, estimator=estimator,
        )

        # Batch callback only needed as a no-op (joblib requires it)
        class Callback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, *args, **kwargs):
                return super().__call__(*args, **kwargs)

        with joblib_callback_patch(Callback):
            try:
                yield
            finally:
                stop_mon.set()
                mon_thread.join(timeout=2.0)
                if use_estimation:
                    stop_est.set()
                    est_thread.join(timeout=1.0)
                # Drain any remaining signals
                import queue as queue_module
                while True:
                    try:
                        signal, item_idx = job_queue.get_nowait()
                        if signal == "done":
                            entry = active_jobs.pop(item_idx, None)
                            if entry:
                                if use_estimation:
                                    job_progress.update(entry[0], completed=100)
                                job_progress.remove_task(entry[0])
                            job_progress.update(overall_task_id, advance=1)
                    except (queue_module.Empty, OSError):
                        break
                for task_id, _ in active_jobs.values():
                    if use_estimation:
                        job_progress.update(task_id, completed=100)
                    job_progress.remove_task(task_id)
                active_jobs.clear()
                job_progress.update(overall_task_id, completed=job_progress.tasks[overall_task_id].total)
    else:
        # Fallback: batch callback mode (no job_queue available)
        completed_jobs = [0]

        class Callback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, *args, **kwargs):
                job_progress.update(overall_task_id, advance=self.batch_size)
                completed_jobs[0] += self.batch_size
                return super().__call__(*args, **kwargs)

        with joblib_callback_patch(Callback):
            try:
                yield
            finally:
                if use_estimation:
                    stop_est.set()
                    est_thread.join(timeout=1.0)
                job_progress.update(overall_task_id, completed=job_progress.tasks[overall_task_id].total)
