# tqdm_backend
> tqdm-based progress rendering for pmap — handles terminal bars, per-job bars, and notebook display via a unified API.
`2 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Thin `pmap()` wrapper that wires backend functions into `run_pmap` from core |
| `progress.py` | All rendering logic: simple bar, per-job bars, notebook stdout/loguru redirection |

<!-- peek -->

## Conventions

- `tqdm.auto` is used (not `tqdm.tqdm`) so the same code auto-selects widget vs. terminal bar in notebooks vs. terminals.
- `run_with_job_bars` falls back to `run_with_simple_bar` when running in a notebook — per-job bars require terminal cursor control that doesn't work in Jupyter.
- loguru is redirected at runtime via `logger.remove()` + `logger.add(write_fn)` so tqdm bars aren't broken by loguru output. The original stderr handler is restored in `finally`. If loguru is not installed, this is silently skipped.
- Thread-backend jobs redirect `sys.stdout` through `NotebookStdoutRedirector` (thread-local buffers) to prevent interleaving. Process-backend jobs skip this (separate processes have separate stdout).

## Gotchas

- `redirect_loguru_to_tqdm` uses a mutable list `pbar_ref = [None]` as a closure workaround — the pbar is assigned after the context manager yields, so the write function must read it lazily via the list.
- `run_with_job_bars` in signal-driven mode prints `'\n' * total_cpus` after completion to clear the per-job bar slots — skipping or double-calling this will corrupt the terminal.
- `log_consumer_tqdm` drains the queue after `stop_event` fires to avoid dropping late log messages; the drain loop must handle `queue.Empty` explicitly.
- `NotebookStdoutRedirector.write` writes directly to the real stdout (bypassing loguru) to avoid re-entrancy deadlocks with loguru's internal lock.
