# demo
> VHS tape scripts and Python demo programs for recording pmap's progress bar features as GIFs.
`19 files | 2026-04-03`

| Entry | Purpose |
|-------|---------|
| `record_all.sh` | Runs all `.tape` files via `vhs` and saves GIFs to `../screenshots/` — the top-level entry point for regenerating README assets |
| `*.tape` | VHS tape scripts that record terminal sessions; each `before-*.tape` variant presumably captures the "before" state for comparison GIFs |
| `simple_bar.py` | Minimal demo: `backend="rich"`, 4 workers, basic `desc=` label |
| `job_bars.py` | Shows `show_job_bars=True` with 10 workers — demonstrates per-job progress panel |
| `loguru_output.py` | Shows loguru/print output routed above live progress bars without scrambling them |
| `tqdm_backend.py` | Shows `backend="tqdm"` for Jupyter-compatible fallback |
| `safe_mode.py` | Demos `safe_mode=True` — error isolation per item |
| `threads.py` | Demos `prefer="threads"` instead of processes |
| `batch_size.py` | Demos custom `batch_size=` argument |
| `sequential.py` | Shows single-worker / sequential execution behavior |

<!-- peek -->

## Conventions
- All demo `.py` files use the `#!/usr/bin/env -S uv run --script` shebang — run them directly (`./simple_bar.py`) or via `uv run demo/simple_bar.py` from the repo root.
- GIF outputs go to `../screenshots/`, NOT inside `demo/` — `record_all.sh` creates that directory at the repo root.
- Each feature has a paired `.tape` + `before-*.tape`; the `before-` tapes likely show the pre-pmap baseline for README comparisons.

## Gotchas
- `record_all.sh` changes directory to the repo root (`cd "$(dirname "$0")/.."`) before running `vhs`, so tape paths assume the repo root as cwd — tapes that call `uv run demo/*.py` are correct; editing tape `Type` lines requires this context.
- `vhs` must be installed separately; `record_all.sh` will silently fail the `gum spin` wrapper if `vhs` is missing.
