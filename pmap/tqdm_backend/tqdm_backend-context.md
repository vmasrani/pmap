# tqdm_backend
> tqdm-based progress rendering for pmap — handles terminal bars, per-job bars, and notebook display via a unified API.
`2 files | 2026-04-03`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Thin `pmap()` entry point — wires `run_pmap` from `core` with the three renderer functions from `progress.py` |
| `progress.py` | All rendering logic: `sequential_map`, `run_with_simple_bar`, `run_with_job_bars`, plus notebook stdout/loguru plumbing |

<!-- peek -->

## Conventions
- `run_pmap` (in `core.py`) owns all dispatch logic; this package only supplies renderer callables injected via `sequential_map_fn`, `run_simple_fn`, `run_job_bars_fn` parameters.
- `tqdm.auto` is used throughout — it auto-selects `tqdm.notebook` or `tqdm.std` based on environment, so the same code path handles both.
- Loguru is patched at runtime via `redirect_loguru_to_tqdm()`: it removes all handlers, adds a custom `write_fn`, then restores `sys.stderr` on exit. Any code that sets up its own loguru handlers before calling `pmap` will have those handlers removed.

## Gotchas
- `run_with_job_bars` silently falls back to `run_with_simple_bar` in notebooks — per-job bars rely on ANSI cursor positioning which Jupyter does not support.
- `NotebookStdoutRedirector` uses thread-local buffers to prevent interleaving from concurrent joblib threads, but it bypasses loguru entirely to avoid re-entrancy deadlocks — log messages in notebooks go through this redirector, not through loguru's normal pipeline.
- The `log_consumer_tqdm` context manager spawns a daemon thread to drain a log queue (used in process-parallel mode). If the consumer thread doesn't drain within 1 second on exit, remaining messages are silently dropped.
- `run_with_job_bars` prints `'\n' * total_cpus` in the `finally` block to clear tqdm's position-indexed bars — this is a side effect visible in terminal output after every parallel call with `show_job_bars=True`.
