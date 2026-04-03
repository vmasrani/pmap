# Plan: uv-style visual polish for pmap progress bars

## Context

pmap's `show_job_bars=True` mode already uses the same architectural pattern as uv (dynamic bar insertion/removal via Rich Progress). The core design is sound. What's missing is the **visual polish** that makes uv's output look clean: a flat (non-paneled) layout, right-aligned descriptions, and tighter bar widths.

**Decisions made:**
- Bar order: start order (no dynamic sorting)
- Layout: flat like uv (no panels/borders)
- Colors: keep existing cyan/blue scheme

## Changes

### 1. Remove Panel wrappers — flat layout

**File:** `pmap/progress_styles.py` — `create_progress_table()` (line 57-98)

Replace the nested `Panel` wrappers with a flat layout:
- Remove both `Panel` imports and usages
- Use a simple `Text` header line: `"Processing tasks (3/60) • 8 CPUs"` rendered above the job bars
- Overall progress bar below (or above) job bars with no border
- Use `Table.grid()` with rows for: header, job_progress, separator, overall_progress

### 2. Right-align job descriptions with fixed-width column

**File:** `pmap/progress_styles.py` — `make_job_description()` (line 14) and `create_progress_columns()` (line 21)

- Change job description TextColumn format to right-align: `"{task.description:>20}"` 
- Use dim styling on the description: `"dim white"` instead of `"bold white"`
- This matches uv's right-aligned, dimmed package names

### 3. Tighten bar width

**File:** `pmap/progress_styles.py` — `create_progress_columns()` (line 21)

- Reduce `bar_width` from 50 to 30 for job bars (matches uv's width)
- Reduce overall bar width similarly
- Remove the `expand=True` on both Progress objects (uv's bars are fixed-width, not expanding)

### 4. Clean up header/title rendering

**File:** `pmap/progress_bars.py` — `DynamicProgressTable` class (line 121-126)

- Update `__rich__` to use the new flat `create_progress_table()` return value
- The header text (`Tasks (3/60) • 8 CPUs`) moves from Panel title to a simple Text row

## Files to modify

1. **`pmap/progress_styles.py`** — main visual changes (remove panels, alignment, bar width)
2. **`pmap/progress_bars.py`** — minor: DynamicProgressTable may need small adjustments

## Verification

1. `uv run demo/job_bars.py` — visually confirm flat layout with right-aligned descriptions
2. `uv run demo/simple_bar.py` — ensure simple bar mode is unaffected  
3. `uv run demo/threads.py` — verify threading mode still works
4. Test with `disable_tqdm=True` — ensure disabled mode still works
