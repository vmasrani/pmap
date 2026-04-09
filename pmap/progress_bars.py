"""Rich progress bar implementations for parallel execution."""
from __future__ import annotations

import contextlib
import math
import queue as queue_module
import threading
import time
from typing import Callable

import joblib
from joblib import Parallel, delayed
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
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
    create_job_progress,
    create_overall_progress,
    compute_panel_height,
    make_job_description,
)

REFRESH_RATE = 15
MAX_VISIBLE_BARS = 20


class _SlotPool:
    """Pre-allocated pool of progress bar slots to avoid add/remove flicker.

    All slots stay visible=True at all times so the rendered line count never
    changes — inactive slots simply show an empty description with no bar
    animation, preventing Rich from reflowing content inside the panel.
    """

    def __init__(self, job_progress, total_cpus: int):
        self._progress = job_progress
        self._lock = threading.Lock()
        self._free: list = []
        for _ in range(total_cpus):
            tid = job_progress.add_task("", total=0, visible=True, start=False)
            self._free.append(tid)

    def acquire(self, description):
        """Activate a free slot with the given description."""
        with self._lock:
            if not self._free:
                return None
            tid = self._free.pop()
        # Start in pulse mode (total=None). The render loop switches to
        # total=100 with dampened progress once estimation is ready.
        self._progress.update(tid, description=description, total=None, completed=0, visible=True)
        # Don't start_task — Rich pulses only when task.started is False
        return tid

    def release(self, tid):
        """Deactivate the slot back to an empty placeholder."""
        self._progress.reset(tid, start=False, total=0, completed=0, description="")
        with self._lock:
            self._free.append(tid)


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

    with Live(progress, refresh_per_second=REFRESH_RATE, transient=False) as live:
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


def run_with_job_bars(mode: ParallelMode, arr: list, n_jobs: int, batch_size, disable_tqdm: bool, desc: str, total_tasks: int, total_cpus: int, kwargs: dict, **_ignored) -> list:
    """Run parallel execution with per-job progress bars and CPU info."""
    overall_progress = create_overall_progress(disable_tqdm)
    overall_task_id = overall_progress.add_task(desc, total=total_tasks)

    job_progress = create_job_progress(disable_tqdm)

    visible_slots = min(total_cpus, MAX_VISIBLE_BARS)
    panel = Panel(
        job_progress,
        title=f"[cyan bold]Tasks (estimating timing...) • {total_cpus} CPUs",
        border_style="dim cyan",
        padding=(1, 1),
        height=compute_panel_height(visible_slots),
        title_align="left",
    )

    display = Group(overall_progress, panel)
    refresh_rate = REFRESH_RATE

    with contextlib.ExitStack() as stack:
        live = stack.enter_context(Live(display, auto_refresh=False, transient=False))
        if mode.log_queue:
            stack.enter_context(log_consumer(mode.log_queue, live))
        stack.enter_context(
            _job_bars_callback(live, job_progress, overall_progress, overall_task_id, total_cpus, panel, total_tasks, mode.job_queue, refresh_rate=refresh_rate)
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


def _start_render_loop(
    live: Live,
    job_queue,
    job_progress,
    overall_progress, overall_task_id,
    active_jobs: dict, lock: threading.Lock,
    slot_pool: _SlotPool,
    panel: Panel, total_tasks: int, total_cpus: int,
    estimator: _JobTimeEstimator | None,
    refresh_rate: float,
) -> tuple[threading.Event, threading.Thread]:
    """Unified render loop: drain signals, update estimations, render once per cycle."""
    stop = threading.Event()
    max_signals = total_cpus * 2

    def run():
        while not stop.is_set():
            # 1. Drain all pending signals in one batch
            drained = 0
            while drained < max_signals:
                try:
                    signal, item_idx = job_queue.get_nowait()
                except (queue_module.Empty, OSError):
                    break
                drained += 1
                now = time.time()
                if signal == "start":
                    task_id = slot_pool.acquire(make_job_description(item_idx + 1))
                    if task_id is not None:
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
                        slot_pool.release(task_id)
                    overall_progress.update(overall_task_id, advance=1)
                    completed = int(overall_progress.tasks[overall_task_id].completed)
                    panel.title = f"[cyan bold]Tasks ({completed}/{total_tasks}) • {total_cpus} CPUs"

            # 2. Update bars: pulse (total=None) during warmup, dampened progress after
            if estimator:
                ref = estimator.reference
                if ref:
                    now = time.time()
                    with lock:
                        for job_task_id, start_time in list(active_jobs.values()):
                            elapsed = now - start_time
                            pct = _dampened_progress(elapsed, ref)
                            if not job_progress._tasks[job_task_id].started:
                                job_progress.start_task(job_task_id)
                            job_progress.update(job_task_id, total=100, completed=pct)

            # 3. Single render
            live.refresh()

            # 4. Sleep until next cycle
            time.sleep(1.0 / refresh_rate)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


@contextlib.contextmanager
def _job_bars_callback(live, job_progress, overall_progress, overall_task_id, total_cpus, panel, total_tasks, job_queue=None, refresh_rate=REFRESH_RATE):
    """Manage per-job progress bars via worker signals (or batch callback fallback)."""
    lock = threading.Lock()
    estimator = _JobTimeEstimator()

    if job_queue is not None:
        # Signal-driven mode: unified render loop handles signals + estimation + refresh
        slot_pool = _SlotPool(job_progress, min(total_cpus, MAX_VISIBLE_BARS))
        active_jobs: dict[int, tuple] = {}  # item_idx -> (task_id, start_time)
        stop_loop, loop_thread = _start_render_loop(
            live, job_queue, job_progress,
            overall_progress, overall_task_id,
            active_jobs, lock,
            slot_pool=slot_pool,
            panel=panel, total_tasks=total_tasks, total_cpus=total_cpus,
            estimator=estimator, refresh_rate=refresh_rate,
        )

        class Callback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, *args, **kwargs):
                return super().__call__(*args, **kwargs)

        with joblib_callback_patch(Callback):
            try:
                yield
            finally:
                stop_loop.set()
                loop_thread.join(timeout=2.0)
                # Drain any remaining signals
                while True:
                    try:
                        signal, item_idx = job_queue.get_nowait()
                        if signal == "done":
                            entry = active_jobs.pop(item_idx, None)
                            if entry:
                                slot_pool.release(entry[0])
                            overall_progress.update(overall_task_id, advance=1)
                    except (queue_module.Empty, OSError):
                        break
                for task_id, _ in active_jobs.values():
                    slot_pool.release(task_id)
                active_jobs.clear()
                overall_progress.update(overall_task_id, completed=overall_progress.tasks[overall_task_id].total)
                # Hide the job panel, show only the final overall bar
                live.update(overall_progress)
                live.refresh()
    else:
        # Fallback: batch callback mode (no job_queue available)
        class Callback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, *args, **kwargs):
                overall_progress.update(overall_task_id, advance=self.batch_size)
                return super().__call__(*args, **kwargs)

        with joblib_callback_patch(Callback):
            try:
                yield
            finally:
                overall_progress.update(overall_task_id, completed=overall_progress.tasks[overall_task_id].total)
                live.update(overall_progress)
                live.refresh()
