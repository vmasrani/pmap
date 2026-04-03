#!/usr/bin/env -S uv run --script
"""Performance benchmark for pmap — captures timing baselines before/after refactoring.

Usage:
    uv run tests/benchmark.py                    # print results
    uv run tests/benchmark.py --output before    # save to screenshots/before/benchmark.json
    uv run tests/benchmark.py --output after     # save to screenshots/after/benchmark.json
    uv run tests/benchmark.py --compare          # compare before vs after
"""
import json
import statistics
import time
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from pmap import pmap

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent


def worker_sleep(i: int, sleep_time: float = 0.1) -> int:
    time.sleep(sleep_time)
    return i * 2


def worker_fast(i: int) -> int:
    return i * 2


def worker_with_logging(i: int) -> int:
    logger.info(f"Processing {i}")
    time.sleep(0.1)
    return i * 2


SCENARIOS = [
    {"name": "simple_bar_processes", "n_items": 20, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Simple"}},
    {"name": "simple_bar_threads", "n_items": 20, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Threads", "prefer": "threads"}},
    {"name": "job_bars_processes", "n_items": 20, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Job Bars", "show_job_bars": True}},
    {"name": "sequential", "n_items": 12, "n_jobs": 1, "backend": "rich",
     "kwargs": {"desc": "Sequential"}},
    {"name": "tqdm_processes", "n_items": 20, "n_jobs": 4, "backend": "tqdm",
     "kwargs": {"desc": "tqdm"}},
    {"name": "tqdm_threads", "n_items": 20, "n_jobs": 4, "backend": "tqdm",
     "kwargs": {"desc": "tqdm threads", "prefer": "threads"}},
    {"name": "fast_workers", "n_items": 100, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Fast"}},
    {"name": "with_logging", "n_items": 15, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Logging"}},
    {"name": "batch_size_1", "n_items": 20, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Batch=1", "batch_size": 1}},
    {"name": "disabled_bar", "n_items": 20, "n_jobs": 4, "backend": "rich",
     "kwargs": {"desc": "Disabled", "disable_tqdm": True}},
]

RUNS_PER_SCENARIO = 3


def run_scenario(scenario: dict) -> float:
    n_items = scenario["n_items"]
    worker = worker_with_logging if scenario["name"] == "with_logging" else (
        worker_fast if scenario["name"] == "fast_workers" else worker_sleep
    )
    items = list(range(n_items))

    start = time.perf_counter()
    pmap(worker, items, n_jobs=scenario["n_jobs"], backend=scenario["backend"],
         **scenario["kwargs"])
    return time.perf_counter() - start


def run_benchmarks() -> list[dict]:
    results = []
    for scenario in SCENARIOS:
        times = [run_scenario(scenario) for _ in range(RUNS_PER_SCENARIO)]
        results.append({
            "name": scenario["name"],
            "n_items": scenario["n_items"],
            "n_jobs": scenario["n_jobs"],
            "backend": scenario["backend"],
            "median_seconds": round(statistics.median(times), 4),
            "min_seconds": round(min(times), 4),
            "max_seconds": round(max(times), 4),
        })
    return results


def print_results(results: list[dict]):
    table = Table(title="pmap Benchmark Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Items", justify="right")
    table.add_column("Jobs", justify="right")
    table.add_column("Backend")
    table.add_column("Median (s)", justify="right", style="green")
    table.add_column("Min (s)", justify="right")
    table.add_column("Max (s)", justify="right")

    for r in results:
        table.add_row(
            r["name"], str(r["n_items"]), str(r["n_jobs"]), r["backend"],
            f"{r['median_seconds']:.4f}", f"{r['min_seconds']:.4f}", f"{r['max_seconds']:.4f}",
        )
    console.print(table)


def compare_results(before: list[dict], after: list[dict]):
    before_map = {r["name"]: r for r in before}
    after_map = {r["name"]: r for r in after}

    table = Table(title="Before vs After Comparison")
    table.add_column("Scenario", style="cyan")
    table.add_column("Before (s)", justify="right")
    table.add_column("After (s)", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Status", justify="center")

    for name in before_map:
        if name not in after_map:
            continue
        b = before_map[name]["median_seconds"]
        a = after_map[name]["median_seconds"]
        pct = ((a - b) / b) * 100 if b > 0 else 0
        status = "[green]OK[/green]" if abs(pct) < 10 else (
            "[red]SLOWER[/red]" if pct > 0 else "[bright_green]FASTER[/bright_green]"
        )
        table.add_row(name, f"{b:.4f}", f"{a:.4f}", f"{pct:+.1f}%", status)

    console.print(table)


app = typer.Typer()


@app.command()
def main(
    output: str = typer.Option(None, help="Save results to screenshots/{output}/benchmark.json"),
    compare: bool = typer.Option(False, help="Compare before vs after benchmarks"),
):
    if compare:
        before_path = PROJECT_ROOT / "screenshots" / "before" / "benchmark.json"
        after_path = PROJECT_ROOT / "screenshots" / "after" / "benchmark.json"
        if not before_path.exists() or not after_path.exists():
            console.print("[red]Need both screenshots/before/benchmark.json and screenshots/after/benchmark.json[/red]")
            raise typer.Exit(1)
        before = json.loads(before_path.read_text())
        after = json.loads(after_path.read_text())
        compare_results(before, after)
        return

    console.print("[bold]Running benchmarks...[/bold]\n")
    results = run_benchmarks()
    print_results(results)

    if output:
        out_path = PROJECT_ROOT / "screenshots" / output / "benchmark.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
        console.print(f"\n[green]Saved to {out_path}[/green]")


if __name__ == "__main__":
    app()
