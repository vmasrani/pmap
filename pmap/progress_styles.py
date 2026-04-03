import shutil
from typing import Any
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.text import Text


class _ConditionalPercentage(TaskProgressColumn):
    """Show percentage only for tasks with a known total (hides for pulse bars)."""

    def render(self, task):
        if task.total is None:
            return Text("", style="cyan")
        return Text(f"{task.percentage:>3.0f}%", style="cyan")

def make_job_description(job_num: int) -> Text:
    """Create a styled job description."""
    return Text.assemble(
        ("", "dim cyan"),
        (f" Job {job_num:02d}", "bold white"),
    )

def create_progress_columns(disable_tqdm: bool = False) -> Progress:
    """Create styled progress bar for job-specific progress."""
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn("dots", style="cyan", speed=1.0),
        BarColumn(
            bar_width=50,
            style="dim cyan",
            complete_style="cyan",
            finished_style="bright_cyan",
        ),
        _ConditionalPercentage(),
        TimeElapsedColumn(),
        disable=disable_tqdm,
        expand=True,
        auto_refresh=False,
    )

def create_progress_table(
    job_progress: Progress,
    total_cpus: int,
    completed_tasks: int,
    total_tasks: int,
) -> Any:
    """Create a styled table with progress information."""
    from rich.panel import Panel
    from rich.table import Table

    progress_table = Table.grid(expand=False)

    if completed_tasks == 0:
        title = f"[cyan bold]Tasks (estimating timing...) • {total_cpus} CPUs"
    else:
        title = f"[cyan bold]Tasks ({completed_tasks}/{total_tasks}) • {total_cpus} CPUs"

    progress_table.add_row(
        Panel(
            job_progress,
            title=title,
            border_style="dim cyan",
            padding=(1, 1),
            height=min(total_cpus + 5, shutil.get_terminal_size().lines - 3),
            width=100,
            title_align="left",
        )
    )

    return progress_table
