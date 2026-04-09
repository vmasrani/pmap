# demo
> VHS tape scripts and Python demo programs for recording pmap's progress bar features as GIFs.
`19 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `record_all.sh` | Orchestrates all `.tape` files via `vhs` to produce GIFs in `screenshots/`; run from repo root |
| `simple_bar.py` | Minimal pmap demo using `backend="rich"` — the baseline progress bar example |
| `job_bars.py` | Realistic multi-job demo with `show_job_bars=True` and variable-duration workloads |
| `loguru_output.py` | Shows loguru log interleaving with Rich progress bars |
| `threads.py` | Demonstrates `prefer="threads"` mode |
| `sequential.py` | Shows fallback behavior with `n_jobs=1` |
| `safe_mode.py` | Demos `safe_mode=True` (error isolation without crash) |
| `tqdm_backend.py` | Shows `backend="tqdm"` as the legacy comparison baseline |
| `batch_size.py` | Illustrates auto vs. fixed `batch_size` effects on throughput |
| `*.tape` | VHS scripts for "after" (current) GIFs — output to `screenshots/` |
| `before-*.tape` | VHS scripts for "before" comparison GIFs — output to `screenshots/before/` |

<!-- peek -->

## Conventions
- Each `.py` demo is a standalone `uv run --script` with no declared dependencies — they import `pmap` directly from the local package (repo root must be on PYTHONPATH or installed in the venv).
- `before-*.tape` mirrors the corresponding `*.tape` exactly except for the `Output` path (`screenshots/before/`). The `screenshots/before/` directory must exist before running; `record_all.sh` only creates `screenshots/`, not the subdirectory.
- All tapes are run from the **repo root** (not the `demo/` dir) — the `record_all.sh` script does `cd "$(dirname "$0")/.."` and all `Type` commands in tapes reference `demo/*.py`.

## Gotchas
- `record_all.sh` only loops over `demo/*.tape` — `before-*.tape` files are also matched by this glob, so running `record_all.sh` generates both current and before GIFs in one pass.
- The `screenshots/before/` output directory is not auto-created; if it's missing, `vhs` will fail silently or error on before-tapes.
- Demo scripts use fixed `time.sleep` values tuned to GIF recording duration. Changing sleep values will cause tapes to cut off mid-execution if `Sleep Xs` in the tape is not also updated.
