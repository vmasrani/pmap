# tests
> Test suite for pmap — covers both backends (rich/tqdm), all execution modes, edge cases, and notebook compatibility.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `test_pmap.py` | Executable script (uv shebang) — run directly via `uv run tests/test_pmap.py`; covers rich+tqdm backends, processes+threads, safe_mode, batch_size, warnings |
| `test_notebook.ipynb` | Jupyter notebook verifying auto-detection of notebook env → tqdm backend; also verifies `show_job_bars` silently degrades to simple bar in notebooks |

<!-- peek -->

## Conventions
- `test_pmap.py` is a standalone script with a uv shebang, not a pytest module. Run it directly: `uv run tests/test_pmap.py`. There are no `test_*` functions — all tests live under `if __name__ == "__main__"`.
- The notebook must be run with `%cd /path/to/pmap` as its first cell (already present) to ensure `from pmap import pmap` resolves correctly from the repo root.

## Gotchas
- `safe_mode=True` returns a list where failed items are dicts with keys `error`, `error_type`, `args`, `kwargs` — not exceptions. Assertions check `isinstance(result, dict) and result['error_type'] == 'ValueError'`.
- In notebooks, `show_job_bars=True` is silently ignored and falls back to a simple tqdm bar — no error is raised, so tests pass but per-job bars are not displayed.
- Auto backend detection uses `is_notebook()` (importable from `pmap`) — `'rich'` in terminal, `'tqdm'` in notebooks.
