# tests
> Test suite for pmap — pytest correctness tests parametrized across backends, plus a standalone performance benchmark.
`3 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `test_pmap_comprehensive.py` | Main pytest suite; correctness tests for all pmap call patterns (processes, threads, job bars, safe_mode, batch_size, edge cases, pmap_df) parametrized over `rich` and `tqdm` backends |
| `benchmark.py` | Standalone CLI script (typer) for timing pmap scenarios; supports `--output before/after` and `--compare` to diff JSON snapshots in `screenshots/` |
| `test_notebook.ipynb` | Notebook-based exploratory tests for interactive/visual validation of progress bar rendering |

<!-- peek -->

## Conventions
- All correctness tests live in class-based groups and are parametrized via `BACKEND_PARAMS = ["rich", "tqdm"]` — adding a new backend requires adding it to this list only.
- Worker functions are defined at module level (not as lambdas/closures) because joblib process-based parallelism requires picklable callables.
- `safe_mode=True` makes pmap catch exceptions and return `{"error_type": ..., ...}` dicts for failed items instead of raising — tests assert on dict structure, not exception propagation.

## Gotchas
- `pmap_df` chunks DataFrames via `np.array_split`, which drops column names (converts to numpy). The `df_worker` test fixture explicitly re-attaches column names — real workers must do the same.
- `benchmark.py` saves JSON snapshots to `screenshots/before/` and `screenshots/after/` relative to the project root; those directories must exist before running `--output`.
- Tests use real `time.sleep` in workers to simulate latency — running the full suite is intentionally slow (~minutes). Use `-k fast` or `-k EdgeCase` to run subsets quickly.
