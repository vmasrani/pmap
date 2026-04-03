# pmap
> Parallel map library wrapping joblib with rich/tqdm progress bars, loguru integration, and Jupyter notebook support.
`9 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `pmap/__init__.py` | Main API — exports `pmap`, `pmap_df`, `run_async`, `safe`; auto-selects backend (rich in terminal, tqdm in notebooks) |
| `pmap/progress_bars.py` | Rich backend progress rendering; monkey-patches `joblib.parallel.BatchCompletionCallBack` to hook into joblib's completion events |
| `pmap/loguru_routing.py` | Strips loguru from function globals before pickling (required for multiprocessing), re-injects it in workers, routes worker logs via a manager queue back to main process |
| `pmap/tqdm_backend/progress.py` | Tqdm backend — used automatically in Jupyter; functionally mirrors `progress_bars.py` but uses `tqdm.auto` instead of Rich Live |
| `pmap/progress_styles.py` | Visual styling helpers for the Rich `show_job_bars=True` mode |
| `tests/test_pmap.py` | Pytest test suite; run with `uv run pytest` |
| `tests/test_notebook.ipynb` | Jupyter notebook test suite for verifying notebook-mode behavior (tqdm backend, auto detection) |
| **pmap/** | Core library package with rich and tqdm backends |
| **tests/** | Test suite covering both terminal and notebook execution modes |

<!-- peek -->

## Conventions
- Backend selection is automatic: `backend='auto'` uses tqdm in Jupyter (Rich `Live` is incompatible with notebooks), rich in terminal. Override with `backend='tqdm'` or `backend='rich'`.
- `loguru_routing.py` strips loguru logger references from the worker function's `__globals__` before pickling — this is required because loguru is not picklable. After joblib finishes, `reinject_loguru` restores them in the main process.
- Worker log output is forwarded via a `multiprocessing.Manager().Queue()` (not a plain `multiprocessing.Queue`) because the managed queue is picklable across processes.
- Thread mode (`prefer='threads'`) skips all the loguru stripping/queue machinery — stdout is shared between threads so no routing is needed.
- `pmap_df` splits DataFrames via `np.array_split` (or `GroupKFold` when `groups=` is given) and calls `pd.concat` on results — the caller's function must return a DataFrame.

## Gotchas
- `joblib.parallel.BatchCompletionCallBack` is globally monkey-patched inside the `progress_with_live` and `rich_joblib_adaptive` context managers. If joblib changes this internal API the progress bars silently break.
- `safe_mode=True` wraps `f` in `safe()` which catches all exceptions and returns a dict `{error, error_type, args, kwargs}` — callers must check results for error dicts rather than expecting exceptions to propagate.
- `show_job_bars=True` spins up a background thread per joblib callback instance to animate per-job progress; estimated progress is based on rolling average job duration and caps at 99% until the job completes.
- `spawn=True` calls `multiprocessing.set_start_method('spawn', force=True)` globally — this is a process-wide side effect and cannot be undone within the same Python process.
- The `ParallelMode` dataclass is duplicated between `progress_bars.py` and `tqdm_backend/progress.py` — they are separate implementations, not shared.
