"""Unified tqdm-based progress bars - single implementation for terminal and notebook."""
from __future__ import annotations

import contextlib
import re
import sys
import threading
from typing import Any, Callable
import queue as queue_module

import joblib
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from .. import is_notebook
from ..core import ParallelMode, joblib_callback_patch

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Map ANSI color codes to CSS colors
_ANSI_COLORS = {
    '30': 'black', '31': 'red', '32': 'green', '33': 'yellow',
    '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white',
    '90': 'gray', '91': '#ff6b6b', '92': '#69db7c', '93': '#ffd43b',
    '94': '#74c0fc', '95': '#e599f7', '96': '#66d9e8', '97': 'white',
}


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text)


_ANSI_STYLES = {
    '1': 'font-weight:bold',
    '2': 'opacity:0.7',
    '3': 'font-style:italic',
}


def _parse_ansi_styles(codes: list[str]) -> tuple[list[str], int]:
    """Parse ANSI codes into CSS styles, returning (styles, reset_count)."""
    styles = []
    resets = 0
    for code in codes:
        if code in ('0', ''):
            resets += 1
        elif code in _ANSI_STYLES:
            styles.append(_ANSI_STYLES[code])
        elif code in _ANSI_COLORS:
            styles.append(f'color:{_ANSI_COLORS[code]}')
    return styles, resets


def ansi_to_html(text: str) -> str:
    """Convert common ANSI escape codes to HTML spans."""
    import html as html_mod
    result = []
    open_spans = 0
    i = 0
    while i < len(text):
        if text[i] == '\x1b' and i + 1 < len(text) and text[i + 1] == '[':
            j = i + 2
            while j < len(text) and text[j] not in 'mGHJK':
                j += 1
            if j < len(text) and text[j] == 'm':
                codes = text[i + 2:j].split(';')
                styles, resets = _parse_ansi_styles(codes)
                for _ in range(resets):
                    result.append('</span>' * open_spans)
                    open_spans = 0
                if styles:
                    result.append(f'<span style="{";".join(styles)}">')
                    open_spans += 1
            i = j + 1
            continue
        else:
            result.append(html_mod.escape(text[i]))
            i += 1
    result.append('</span>' * open_spans)
    return ''.join(result)


class NotebookStdoutRedirector:
    """Thread-safe stdout proxy that formats output like loguru for notebooks.

    Uses thread-local buffers so concurrent threads don't interleave.
    Writes directly to the real stdout (not through loguru) to avoid
    re-entrancy deadlocks with loguru's internal lock.
    """
    def __init__(self, real_stdout):
        self._real = real_stdout
        self._local = threading.local()
        self._lock = threading.Lock()

    def _get_buffer(self) -> str:
        return getattr(self._local, 'buf', '')

    def _set_buffer(self, value: str) -> None:
        self._local.buf = value

    def write(self, msg: str) -> int:
        if not msg:
            return 0
        buf = self._get_buffer() + msg
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            text = strip_ansi(line).strip()
            if text:
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                formatted = f"{ts} | INFO     | {text}\n"
                with self._lock:
                    self._real.write(formatted)
                    self._real.flush()
        self._set_buffer(buf)
        return len(msg)

    def flush(self) -> None:
        buf = self._get_buffer()
        text = strip_ansi(buf).strip()
        if text:
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S")
            formatted = f"{ts} | INFO     | {text}\n"
            with self._lock:
                self._real.write(formatted)
                self._real.flush()
        self._set_buffer('')

    def __getattr__(self, name):
        return getattr(self._real, name)


@contextlib.contextmanager
def notebook_stdout_filter():
    """Route stdout through loguru in notebooks. No-op in terminals."""
    if not is_notebook():
        yield
        return
    old_stdout = sys.stdout
    sys.stdout = NotebookStdoutRedirector(old_stdout)
    try:
        yield
    finally:
        sys.stdout.flush()
        sys.stdout = old_stdout


def safe_write(pbar, message: str) -> None:
    """Write message compatible with both terminal and notebook."""
    if is_notebook():
        from IPython.display import display, HTML
        html = ansi_to_html(message)
        display(HTML(f"<pre style='margin:0;padding:0'>{html}</pre>"))
    else:
        pbar.write(message)


def sequential_map(f: Callable, arr: list, desc: str, disable: bool) -> list:
    """Sequential map with tqdm progress bar."""
    if disable:
        return [f(item) for item in arr]

    results = []
    with (notebook_stdout_filter(), redirect_loguru_to_tqdm() as pbar_ref):
        pbar = tqdm(arr, desc=desc)
        pbar_ref[0] = pbar
        results.extend(f(item) for item in pbar)
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
        elif in_notebook:
            from IPython.display import display, HTML
            display(HTML(f"<pre style='margin:0;padding:0'>{ansi_to_html(msg)}</pre>"))
        else:
            print(msg)

    try:
        import loguru
        loguru.logger.remove()
        handler_id = loguru.logger.add(
            write_fn,
            colorize=True,
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

    def _make_calls():
        if mode.job_queue:
            return (delayed(mode.wrapped_func)(idx, item) for idx, item in enumerate(arr))
        return (delayed(mode.wrapped_func)(i) for i in arr)

    try:
        with joblib_callback_patch(TqdmCallback), log_consumer_tqdm(mode.log_queue, pbar):
            if mode.using_threads:
                with notebook_stdout_filter(), redirect_loguru_to_tqdm() as pbar_ref:
                    pbar_ref[0] = pbar
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        _make_calls()
                    )
            else:
                results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                    _make_calls()
                )
    finally:
        pbar.close()

    return results


def run_with_job_bars(mode: ParallelMode, arr: list, n_jobs: int, batch_size,
                      disable_tqdm: bool, desc: str, total_tasks: int,
                      total_cpus: int, kwargs: dict, **_ignored) -> list:
    """Run with per-job tqdm progress bars."""
    if is_notebook():
        return run_with_simple_bar(mode, arr, n_jobs, batch_size,
                                   disable_tqdm, desc, kwargs)

    overall = tqdm(total=total_tasks, desc=desc, position=0,
                   disable=disable_tqdm, leave=True)
    active_bars = {}
    bar_lock = threading.Lock()

    def _make_delayed_calls():
        if mode.job_queue:
            return (delayed(mode.wrapped_func)(idx, item) for idx, item in enumerate(arr))
        return (delayed(mode.wrapped_func)(i) for i in arr)

    if mode.job_queue:
        # Signal-driven mode: monitor thread manages per-job bars
        stop_event = threading.Event()

        def _monitor():
            bar_position = [1]
            while not stop_event.is_set():
                try:
                    signal, item_idx = mode.job_queue.get(timeout=0.05)
                except (queue_module.Empty, OSError):
                    continue

                with bar_lock:
                    if signal == "start":
                        pos = bar_position[0]
                        bar_position[0] = (bar_position[0] % total_cpus) + 1
                        bar = tqdm(total=1, desc=f"  Job {item_idx + 1:>4}", position=pos,
                                  leave=False, disable=disable_tqdm,
                                  bar_format='{desc}: {bar} | {elapsed}')
                        active_bars[item_idx] = bar
                    elif signal == "done":
                        bar = active_bars.pop(item_idx, None)
                        if bar:
                            bar.update(1)
                            bar.close()
                        overall.update(n=1)

        monitor = threading.Thread(target=_monitor, daemon=True)
        monitor.start()

        # No-op batch callback (overall is updated by monitor)
        class TqdmJobCallback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, out):
                return super().__call__(out)

        try:
            with joblib_callback_patch(TqdmJobCallback), log_consumer_tqdm(mode.log_queue, overall):
                if mode.using_threads:
                    with notebook_stdout_filter(), redirect_loguru_to_tqdm() as pbar_ref:
                        pbar_ref[0] = overall
                        results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                            _make_delayed_calls()
                        )
                else:
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        _make_delayed_calls()
                    )
        finally:
            stop_event.set()
            monitor.join(timeout=2.0)
            # Drain remaining signals
            while True:
                try:
                    signal, item_idx = mode.job_queue.get_nowait()
                    if signal == "done":
                        bar = active_bars.pop(item_idx, None)
                        if bar:
                            bar.update(1)
                            bar.close()
                        overall.update(n=1)
                except (queue_module.Empty, OSError):
                    break
            with bar_lock:
                for bar in active_bars.values():
                    bar.close()
            overall.close()
            print('\n' * total_cpus, end='')
    else:
        # Fallback: batch callback mode
        job_counter = [0]

        class TqdmJobCallback(joblib.parallel.BatchCompletionCallBack):
            def __call__(self, out):
                with bar_lock:
                    overall.update(n=self.batch_size)
                    job_counter[0] += 1
                    job_num = job_counter[0]

                    while len(active_bars) >= total_cpus:
                        oldest = min(active_bars.keys())
                        active_bars[oldest].close()
                        del active_bars[oldest]

                    pos = (len(active_bars) % total_cpus) + 1
                    bar = tqdm(total=1, desc=f"  Job {job_num:>4}", position=pos,
                              leave=False, disable=disable_tqdm,
                              bar_format='{desc}: {bar} | {elapsed}')
                    bar.update(1)
                    active_bars[job_num] = bar

                return super().__call__(out)

        try:
            with joblib_callback_patch(TqdmJobCallback), log_consumer_tqdm(mode.log_queue, overall):
                if mode.using_threads:
                    with notebook_stdout_filter(), redirect_loguru_to_tqdm() as pbar_ref:
                        pbar_ref[0] = overall
                        results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                            _make_delayed_calls()
                        )
                else:
                    results = Parallel(n_jobs=n_jobs, batch_size=batch_size, **kwargs)(
                        _make_delayed_calls()
                    )
        finally:
            with bar_lock:
                for bar in active_bars.values():
                    bar.close()
            overall.close()
            print('\n' * total_cpus, end='')

    return results
