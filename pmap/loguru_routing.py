"""Loguru routing and stdout redirection for parallel workers.

This module handles:
- Stripping loguru from function globals for pickling
- Re-injecting loguru in worker processes
- Redirecting stdout to loguru so print() appears above progress bars
- Forwarding log messages from workers to main process via queue
"""
from __future__ import annotations

import contextlib
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class LoguruConfig:
    """Configuration for loguru in worker processes."""
    stripped_names: set[str]
    log_queue: Any  # multiprocessing.Queue


class LoguruStdoutRedirector:
    """Redirects stdout writes to loguru so they appear above progress bar."""
    def __init__(self):
        self._buffer = ""

    def write(self, msg: str) -> None:
        if not msg:
            return
        self._buffer += msg
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                with contextlib.suppress(Exception):
                    from loguru import logger
                    logger.opt(depth=2).info(line.rstrip())

    def flush(self) -> None:
        if self._buffer.strip():
            with contextlib.suppress(Exception):
                from loguru import logger
                logger.opt(depth=2).info(self._buffer.rstrip())
            self._buffer = ""


def create_queue_sink(log_queue):
    """Create a loguru sink that writes to a multiprocessing queue."""
    def sink(message):
        with contextlib.suppress(Exception):
            log_queue.put_nowait(str(message).rstrip())

    return sink


def start_log_consumer(log_queue, live):
    """Start a thread that consumes log messages and prints above progress bar."""
    import queue as queue_module

    stop_event = threading.Event()

    def consumer():
        while not stop_event.is_set():
            try:
                message = log_queue.get(timeout=0.1)
                if message and live:
                    live.console.print(message)
            except queue_module.Empty:
                continue
        while True:
            try:
                message = log_queue.get_nowait()
                if message and live:
                    live.console.print(message)
            except queue_module.Empty:
                break

    thread = threading.Thread(target=consumer, daemon=True)
    thread.start()
    return stop_event, thread


def find_loguru_names(f: Callable) -> set[str]:
    """Find loguru Logger names in function globals without mutating."""
    names: set[str] = set()
    with contextlib.suppress(ImportError):
        from loguru._logger import Logger
        globs: dict[str, Any] = getattr(f, '__globals__', {})
        for name, value in globs.items():
            if isinstance(value, Logger):
                names.add(name)
    return names


def strip_loguru_from_globals(f: Callable, names: set[str]) -> None:
    """Remove loguru Logger from function globals to allow pickling."""
    globs: dict[str, Any] | None = getattr(f, '__globals__', None)
    if not names or globs is None:
        return
    for name in names:
        if name in globs:
            globs[name] = None


def setup_worker_loguru(config: LoguruConfig) -> None:
    """Configure loguru in worker process."""
    if config.log_queue is None:
        return
    with contextlib.suppress(ImportError):
        from loguru import logger
        logger.remove()
        logger.add(
            create_queue_sink(config.log_queue),
            format="{time:HH:mm:ss} | {level: <8} | {message}",
            colorize=True
        )


def reinject_loguru(f: Callable, stripped_names: set[str]) -> None:
    """Re-inject loguru into function globals after pickle."""
    globs: dict[str, Any] | None = getattr(f, '__globals__', None)
    if not stripped_names or globs is None:
        return
    with contextlib.suppress(ImportError):
        from loguru import logger
        for name in stripped_names:
            if globs.get(name) is None:
                globs[name] = logger


def make_worker_wrapper(f: Callable, config: LoguruConfig) -> Callable:
    """Create wrapper that routes all output through loguru."""
    def wrapper(*args, **kwargs):
        setup_worker_loguru(config)
        reinject_loguru(f, config.stripped_names)

        old_stdout = sys.stdout
        sys.stdout = LoguruStdoutRedirector()
        try:
            return f(*args, **kwargs)
        finally:
            sys.stdout.flush()
            sys.stdout = old_stdout
    return wrapper


@contextlib.contextmanager
def redirect_loguru_to_live(live):
    """Redirect loguru output to print above the Rich Live display."""
    if live is None:
        yield
        return

    try:
        import loguru
        loguru.logger.remove()
        handler_id = loguru.logger.add(
            lambda m: live.console.print(m, end=""),
            colorize=True,
            format="{time:HH:mm:ss} | {level: <8} | {message}"
        )
        try:
            yield
        finally:
            loguru.logger.remove(handler_id)
            loguru.logger.add(sys.stderr)
    except ImportError:
        yield


@contextlib.contextmanager
def log_consumer(log_queue: Any, live: Any):
    """Context manager for log consumer thread lifecycle."""
    if log_queue is None or live is None:
        yield
        return

    stop_event, thread = start_log_consumer(log_queue, live)
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)
