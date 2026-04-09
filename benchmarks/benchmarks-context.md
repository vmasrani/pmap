# benchmarks
> Side-by-side competitor benchmarks comparing pmap against other parallel-map libraries with progress bars.
`9 files | 2026-04-06`

| Entry | Purpose |
|-------|---------|
| `bench_pmap.py` | pmap under test — exercises simple bar, per-job bars (`show_job_bars=True`), and `safe_mode` |
| `bench_baseline.py` | stdlib `multiprocessing.Pool` reference — no progress bar, no deps |
| `bench_joblib_progress.py` | joblib + joblib-progress (Rich wrapper for joblib.Parallel) |
| `bench_mpire.py` | mpire competitor benchmark |
| `bench_parmap.py` | parmap competitor benchmark |
| `bench_p_tqdm.py` | p-tqdm competitor benchmark |
| `bench_pqdm.py` | pqdm competitor benchmark |
| `bench_parallelbar.py` | parallelbar competitor benchmark |
| `bench_tqdm_concurrent.py` | tqdm-concurrent competitor benchmark |

<!-- peek -->

## Conventions
- All benchmarks use the same workload: Monte Carlo Black-Scholes option pricing, 80 tasks × 50k sims × 200 steps, targeting ~30s on 8 cores. Results are directly comparable across scripts.
- Each file is a self-contained uv script with inline dependencies (`# /// script` block). Run any benchmark with `uv run bench_<name>.py` — no venv setup needed.
- `bench_pmap.py` uses a local path dependency (`pmap @ file:///...`) — this path is hardcoded to the author's machine and must be updated for other environments.

## Gotchas
- The local path in `bench_pmap.py` line 4 is absolute to the original author's filesystem. Running on another machine requires updating this path or installing pmap from PyPI/git.
- All scripts hardcode `n_jobs=8` — does not auto-detect core count. Results vary on machines with fewer/more cores.
- `print()` inside `price_option` fires every 30th seed; this stdout noise is intentional to test output routing, not a bug.
