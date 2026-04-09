# pmap
> Core package for parallel map with Rich/tqdm dual-backend progress bars, loguru-aware process/thread dispatch, and per-job animated bars.
`6 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Public API: `pmap`, `pmap_df`, `run_async`, `safe`, `is_notebook` — entry point for all callers |
| `core.py` | Shared orchestration: `prepare_parallel_mode` strips/re-injects loguru for pickling; `run_pmap` dispatches to backend-specific fns |
| `progress_bars.py` | Rich backend: `_SlotPool` pre-allocates fixed progress slots to prevent flicker; `_JobTimeEstimator` EMA-based dampened estimation |
| `loguru_routing.py` | Strips loguru from function globals before pickling, re-injects in worker; routes print/loguru above live progress bar |
| `progress_styles.py` | Rich widget factories: overall bar, per-job bar, `_ConditionalPercentage` hides % for empty slots |
| **tqdm_backend/** | tqdm-based backend for Jupyter notebooks; shares `core.run_pmap` orchestration |

<!-- peek -->

## Conventions

- **Backend selection**: `backend='auto'` picks `'tqdm'` in Jupyter (detected via `is_notebook()`) and `'rich'` in terminals. Force with `backend='rich'` or `backend='tqdm'`.
- **Process vs thread mode**: `prefer='threads'` (passed via `**kwargs`) skips all loguru stripping and uses `queue.Queue` instead of `manager.Queue`. Thread mode routes loguru via `redirect_loguru_to_live`, not a queue consumer thread.
- **`show_job_bars=True` forces `batch_size=1`** — done intentionally so every individual item appears as a worker signal. Callers passing a custom `batch_size` have it silently overridden.
- **`run_pmap` signature**: backend-specific functions (`sequential_map_fn`, `run_simple_fn`, `run_job_bars_fn`) are injected as callables — the same `core.run_pmap` drives both Rich and tqdm backends.
- **`pmap_df`**: splits DataFrame with `numpy.array_split` or `GroupKFold`, then concats — result order is preserved only if `axis=0` and no group splitting reorders rows.

## Gotchas

- **Loguru pickling**: `prepare_parallel_mode` calls `strip_loguru_from_globals` before joblib serializes the function, then `reinject_loguru` in a `finally` block. If an exception escapes `run_pmap`'s `try/finally`, loguru stays stripped from the function's globals permanently in that process.
- **`_SlotPool` slots start unstarted** (`start=False`): Rich pulses only tasks where `task.started is False` and `total is None`. Calling `start_task` prematurely stops the pulse; the render loop calls it only when estimation data is available.
- **`job_queue` changes function signature for `show_job_bars`**: when `job_queue` is set, workers receive `(idx, item)` tuples instead of bare `item` — the wrapper in `loguru_routing.make_signaling_wrapper` handles unpacking, so the user's function still sees only `item`.
- **`multiprocessing.Manager` overhead**: process mode always spawns a Manager for the log queue. For small arrays or fast functions, thread mode (`prefer='threads'`) is significantly cheaper.
- **Panel height is fixed at creation** (`compute_panel_height`): computed once from terminal size. Resizing the terminal mid-run will not reflow the panel.
- **`joblib_callback_patch` is not thread-safe**: it patches `joblib.parallel.BatchCompletionCallBack` globally — concurrent pmap calls in separate threads would corrupt each other's callback.
- **`spawn=True`** calls `set_start_method('spawn', force=True)` globally — process-global and irreversible within the session.
- **`pmap_df`** requires `sklearn` (`GroupKFold`) and `numpy` even for non-grouped use — not declared as hard package dependencies.
