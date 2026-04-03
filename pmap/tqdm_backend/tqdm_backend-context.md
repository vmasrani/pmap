# tqdm_backend
> tqdm-based parallel map backend using joblib under the hood; works in both terminals and Jupyter notebooks.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Public `pmap` entrypoint — orchestrates mode selection, loguru cleanup, and manager shutdown |
| `progress.py` | All parallel execution logic: `ParallelMode` dataclass, progress bar strategies, loguru→tqdm routing |

<!-- peek -->

## Conventions
- `tqdm.auto` is used (not `tqdm.tqdm`) so the same code renders as a widget in notebooks and a text bar in terminals.
- Progress is tracked by monkey-patching `joblib.parallel.BatchCompletionCallBack` at runtime; the original is always restored in a `finally` block. Any future joblib API change to that callback will silently break progress updates.
- Loguru routing differs by execution mode: thread workers redirect via `redirect_loguru_to_tqdm` context manager; process workers use a `multiprocessing.Manager().Queue()` drained by a daemon thread (`log_consumer_tqdm`).
- `desc` is popped from `**kwargs` before forwarding to `joblib.Parallel` — passing it directly to joblib would cause a TypeError.
- `reinject_loguru` is called in `pmap`'s `finally` to restore loguru sinks in the main process after parallel execution.

## Gotchas
- `show_job_bars=True` silently falls back to a simple bar when running inside a Jupyter notebook — multi-position tqdm bars don't render correctly in notebook output cells.
- Process-mode startup always creates a `multiprocessing.Manager()` (and its child process); the manager is shut down in `pmap`'s `finally`. A crash before that point leaks the manager process.
- Loguru handlers are stripped from the worker function's globals before forking and reinjected after. Any code inspecting those globals between fork and rejoin will see them missing.
- `n_jobs=1` bypasses joblib entirely and runs `sequential_map` — the loguru-stripping and manager setup in `prepare_parallel_mode` are never executed, so loguru works normally.
- `spawn=True` calls `multiprocessing.set_start_method('spawn', force=True)` globally and permanently; using it more than once in a session can cause errors.
- `run_with_job_bars` prints `'\n' * total_cpus` unconditionally in `finally` to clear ghost tqdm lines — this leaves extra blank lines in terminal output even when `disable_tqdm=True`.
