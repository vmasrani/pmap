# pmap
> Core package for parallel map with rich/tqdm progress bars, dual-backend design, and loguru-aware process/thread dispatch.
`7 files | 2026-04-03`

| Entry | Purpose |
|-------|---------|
| `__init__.py` | Public API: `pmap`, `pmap_df`, `run_async`, `safe`. Backend selection (`auto`/`rich`/`tqdm`) and notebook detection live here. |
| `core.py` | Shared orchestration used by both backends — `run_pmap()` entry point, `prepare_parallel_mode()`, and joblib callback patcher. |
| `progress_bars.py` | Rich backend implementations: simple bar (`run_with_simple_bar`), per-job bars (`run_with_job_bars`), and `sequential_map`. |
| `loguru_routing.py` | Strips loguru from function globals before pickling, re-injects it in workers, and routes worker print/log output above the progress bar via a queue. |
| `progress_styles.py` | Rich layout helpers — column definitions and table construction for `show_job_bars` mode. |
| **tqdm_backend/** | tqdm-based progress rendering for pmap — handles terminal bars, per-job bars, and notebook display via a unified API. |

<!-- peek -->

## Conventions
- Backend selection at call site: `backend='auto'` (default) switches to `'tqdm'` in notebooks because Rich's `Live` doesn't render in Jupyter. Override explicitly if needed.
- `run_pmap()` in `core.py` is backend-agnostic — it accepts `safe_fn`, `sequential_map_fn`, `run_simple_fn`, `run_job_bars_fn` as callables so both backends can reuse the same orchestration logic.
- Progress bars hook into joblib via monkeypatching `joblib.parallel.BatchCompletionCallBack`. The patch is always restored in a `finally` block.
- `prefer='threads'` bypasses all loguru stripping/queue setup — thread mode shares stdout directly.

## Gotchas
- Loguru is **stripped from function globals before pickling** and re-injected after. If a worker function closes over a loguru `logger` not in its own module's globals, it won't be found by `find_loguru_names` and will cause a pickling error in process mode. Use `prefer='threads'` as a workaround.
- `multiprocessing.Manager()` is created for every process-mode call, including when `n_jobs=1` (which short-circuits to `sequential_map` before that point). Manager is always shut down in `finally`.
- `spawn=True` calls `set_start_method('spawn', force=True)` globally — this is process-global and irreversible within the session.
- Per-job bars (`show_job_bars=True`) use a background estimation thread (EMA of per-batch time) to animate progress. Bars show at most `min(n_jobs, len(arr))` concurrent entries.
- `pmap_df` requires `sklearn` (`GroupKFold`) and `numpy` even for non-grouped use — these are not declared as hard dependencies in the package.
