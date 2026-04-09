# pmap
> Parallel map library with Rich/tqdm progress bars, loguru integration, and notebook-compatible backends.
`8 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `pmap/__init__.py` | Public API — `pmap`, `pmap_df`, `run_async`, `safe`, `is_notebook`; backend dispatch lives here |
| `pmap/core.py` | Shared orchestration used by both backends: `prepare_parallel_mode`, `run_pmap`, joblib callback patch |
| `pmap/progress_bars.py` | Rich backend progress bar implementations; `_SlotPool` prevents flicker by pre-allocating fixed slots |
| `pmap/loguru_routing.py` | Strips loguru from function globals before pickling; re-injects in workers; routes `print()` and loguru through a queue to appear above progress bars |
| `pmap/progress_styles.py` | Visual config for Rich bars (column layout, panel height, slot descriptions) |
| `pyproject.toml` | Package metadata; runtime deps are joblib, loguru, rich, tqdm |
| `PLAN.md` | Design notes and feature roadmap — useful context for architectural decisions |
| **pmap/tqdm_backend/** | Alternate backend used automatically in Jupyter; same `run_pmap` core, different progress renderer |
| **tests/** | pytest suite + notebook test; `benchmark.py` for perf comparison |
| **benchmarks/** | Standalone benchmark scripts |
| **demo/** | Demo scripts and screenshots |

<!-- peek -->

## Conventions

- Backend is selected at call time: `backend='auto'` resolves to `'tqdm'` in notebooks (`is_notebook()` checks for `ZMQInteractiveShell`), `'rich'` otherwise. Force with `backend='rich'` or `backend='tqdm'`.
- Both backends share `core.run_pmap` — they differ only in which `sequential_map_fn`, `run_simple_fn`, and `run_job_bars_fn` callables are passed in.
- `prefer='threads'` skips loguru stripping/reinjection and the multiprocessing Manager entirely (no pickling needed).
- `show_job_bars=True` forces `batch_size=1` internally to keep all worker slots visible.
- `safe_mode=True` wraps the function with `safe()`, returning `{'error', 'error_type', 'args', 'kwargs'}` dicts instead of raising.

## Gotchas

- In process mode (default), loguru is **stripped from function globals before pickling** and reinjected in each worker. If the user function closes over a loguru logger variable, it must be imported inside the function body rather than captured from the outer scope.
- `_SlotPool` in `progress_bars.py` pre-allocates all slots at startup and keeps them `visible=True` with `start=False`. Calling `start_task` outside the intended code path breaks the pulse animation — slots pulse only when `task.started is False`.
- `joblib_callback_patch` monkey-patches `joblib.parallel.BatchCompletionCallBack` for the duration of the parallel call. Nested `pmap` calls will fight over this patch.
- `pmap_df` requires `scikit-learn` (for `GroupKFold`) even when `groups=` is not used; it is a dev dependency, not a runtime one.
- The Rich backend does not work in Jupyter — `is_notebook()` guards this, but forcing `backend='rich'` in a notebook will produce broken output.
- `run_async` returns a `multiprocessing.Queue`, not a future — callers must call `.get()` to retrieve results.
