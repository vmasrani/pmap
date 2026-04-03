# pmap
> Parallel map library wrapping joblib with Rich/tqdm progress bars, loguru routing, and notebook auto-detection.
`4 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Main public API — `pmap`, `pmap_df`, `run_async`, `safe`; dispatches to rich or tqdm backend |
| `loguru_routing.py` | Strips loguru from worker globals before pickling, re-injects after; routes worker stdout/logs through a queue so output appears above progress bars |
| `progress_bars.py` | Rich-based progress bar implementations (simple bar and per-job bars); integrates with joblib via callbacks |
| `progress_styles.py` | Visual styling helpers for Rich progress columns and job descriptions |
| **tqdm_backend/** | tqdm-based parallel map backend using joblib under the hood; works in both terminals and Jupyter notebooks. |

<!-- peek -->

## Conventions

- Backend selection is automatic: `backend='auto'` uses `tqdm` in Jupyter notebooks (Rich `Live` does not render in notebooks) and `rich` in terminals. Pass `backend='rich'` or `backend='tqdm'` to override.
- `prefer='threads'` skips all loguru stripping and queue setup entirely — thread mode uses no log routing because threads share stdout.
- `pmap_df` splits a DataFrame into `n_chunks` (default 100) before parallel mapping, then `pd.concat`s results — callee function must accept and return a DataFrame slice.
- `safe_mode=True` wraps `f` with the `safe()` decorator, catching all exceptions and returning `{'error': ..., 'error_type': ..., 'args': ..., 'kwargs': ...}` dicts rather than raising.

## Gotchas

- Loguru `logger` objects are not picklable. `loguru_routing.py` mutates `f.__globals__` directly (sets loguru names to `None`) before spawning workers and restores them in a `finally` block via `reinject_loguru`. This mutation is global — if `pmap` is interrupted mid-run, loguru stays `None` in the caller's module until the next successful `pmap` call completes the `finally`.
- `multiprocessing.Manager()` is started for every process-mode `pmap` call (to create a shared queue). `manager.shutdown()` is called in `finally` — failing to reach `finally` (e.g., `SIGKILL`) leaves a manager process orphaned.
- `spawn=True` calls `multiprocessing.set_start_method('spawn', force=True)` globally and permanently for the process lifetime, not just for that call.
- `n_jobs=1` bypasses joblib entirely and runs sequentially with a simple tqdm loop — useful for debugging.
