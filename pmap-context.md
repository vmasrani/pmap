# pmap
> Parallel map library with Rich/tqdm progress bars, loguru integration, and notebook-compatible backends.
`7 files | 2026-04-03`

| Entry | Purpose |
|-------|---------|
| `pyproject.toml` | Package config; entry point for deps (joblib, rich, tqdm, loguru, ipywidgets) |
| **pmap/** | Main package — `__init__.py` is the public API; `core.py` is shared orchestration logic |
| **demo/** | VHS tape scripts and demo `.py` files for recording GIFs of each feature |
| **tests/** | Pytest suite + benchmark + Jupyter notebook for notebook-mode testing |
| **screenshots/** | Static assets; not code |

<!-- peek -->

## Conventions
- Public API surface: `pmap`, `pmap_df`, `run_async`, `safe` — all imported from `pmap/__init__.py`.
- `backend='auto'` selects `'tqdm'` in Jupyter (Rich Live doesn't work in notebooks) and `'rich'` in terminals. Override explicitly with `backend='tqdm'` or `backend='rich'`.
- `core.py` is a shared orchestration layer used by BOTH backends — the Rich and tqdm backends inject their own `sequential_map_fn`, `run_simple_fn`, `run_job_bars_fn` callables into `run_pmap()` rather than subclassing.
- In process mode (default), all stdout/print output from workers is intercepted by `LoguruStdoutRedirector` and re-emitted via loguru so it appears above the progress bar. In thread mode (`prefer='threads'`), output goes directly to stdout.

## Gotchas
- Loguru is stripped from function globals before pickling (for subprocess workers) and re-injected inside each worker — functions that reference `logger` as a module-level global will have it temporarily removed. This is handled transparently by `loguru_routing.py`.
- `pmap_df` uses `sklearn.model_selection.GroupKFold` for group-aware splitting — requires scikit-learn, which is listed as a hard dependency even for non-ML use.
- `safe_mode=True` wraps `f` with the `safe()` decorator, which catches ALL exceptions and returns a dict `{'error': ..., 'error_type': ..., 'args': ..., 'kwargs': ...}` instead of raising. Callers must check return types.
- `run_async` returns a `multiprocessing.Queue`, not a future — callers must call `.get()` on the queue to retrieve results.
- joblib's `BatchCompletionCallBack` is monkey-patched via `joblib_callback_patch` context manager to enable per-job progress bars; this modifies a private joblib internal.
