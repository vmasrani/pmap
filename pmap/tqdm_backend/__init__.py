"""Unified tqdm-based pmap - works in terminals and notebooks."""
from __future__ import annotations

from .. import safe
from ..core import run_pmap
from .progress import (
    sequential_map,
    run_with_simple_bar,
    run_with_job_bars,
)

__all__ = ['pmap']


def pmap(f, arr, n_jobs=-1, disable_tqdm=False, safe_mode=False, spawn=False,
         batch_size='auto', show_job_bars=False, **kwargs):
    """Parallel map with tqdm progress bar (works in terminals and notebooks)."""
    return run_pmap(
        f, arr, n_jobs=n_jobs, disable_tqdm=disable_tqdm, spawn=spawn,
        batch_size=batch_size, show_job_bars=show_job_bars,
        safe_mode=safe_mode,
        safe_fn=safe, sequential_map_fn=sequential_map,
        run_simple_fn=run_with_simple_bar, run_job_bars_fn=run_with_job_bars,
        **kwargs,
    )
