# tests
> Test suite for pmap — pytest correctness tests parametrized across backends, plus a standalone performance benchmark.
`3 files | 2026-04-03`

| Entry | Purpose |
|-------|---------|
| `test_pmap_comprehensive.py` | Pytest suite covering correctness across `rich` and `tqdm` backends, safe_mode, batch_size, edge cases, and `pmap_df`; run with `uv run pytest tests/test_pmap_comprehensive.py -v` |
| `benchmark.py` | Standalone CLI script (typer) that times 10 named scenarios with 3 runs each; supports `--output before/after` and `--compare` to diff JSON baselines saved under `screenshots/` |
| `test_notebook.ipynb` | Interactive notebook-based tests — verifies pmap works correctly inside Jupyter (auto backend detection path) |

<!-- peek -->

## Conventions
- All correctness tests are parametrized via `BACKEND_PARAMS = ["rich", "tqdm"]` — every test class runs twice automatically.
- Worker functions are defined at module level (not inside tests) because joblib spawns subprocesses that must be able to import them; lambdas or nested functions will fail with process-based parallelism.
- `benchmark.py` uses the uv shebang and is run directly (`uv run tests/benchmark.py`), not via pytest.

## Gotchas
- `safe_mode=True` returns a dict with keys `error_type`, `args`, `kwargs` on failure — tests assert this shape explicitly; changing the error dict schema will break assertions at lines 158-162.
- `test_large_array` uses 500 items with `worker_fast` (no sleep) — if batch_size auto-calculation changes, this test can silently produce wrong ordering.
- The benchmark saves JSON baselines to `screenshots/before/benchmark.json` and `screenshots/after/benchmark.json` relative to the project root; that directory must exist before using `--output`.
