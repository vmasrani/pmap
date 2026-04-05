import shutil
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    MofNCompleteColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.text import Text


class _ConditionalPercentage(TaskProgressColumn):
    """Show percentage only for active tasks (hides for inactive/empty slots)."""

    def render(self, task):
        if task.total is None or task.total == 0:
            return Text("", style="cyan")
        return Text(f"{task.percentage:>3.0f}%", style="cyan")


def make_job_description(job_num: int) -> Text:
    """Create a styled job description."""
    return Text.assemble(
        ("", "dim cyan"),
        (f" Job {job_num:02d}", "bold white"),
    )


def create_overall_progress(disable: bool = False) -> Progress:
    """Create the aggregate progress bar (M/N, percentage, time remaining)."""
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            bar_width=50,
            style="dim cyan",
            complete_style="cyan",
            finished_style="bright_cyan",
        ),
        TextColumn("{task.percentage:>3.0f}%", style="cyan"),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        disable=disable,
    )


def create_job_progress(disable: bool = False) -> Progress:
    """Create per-job progress bar columns (spinner, bar, elapsed)."""
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        SpinnerColumn("dots", style="cyan", speed=1.5),
        BarColumn(
            bar_width=40,
            style="dim cyan",
            complete_style="cyan",
            finished_style="bright_cyan",
        ),
        _ConditionalPercentage(),
        TimeElapsedColumn(),
        disable=disable,
    )


def compute_panel_height(total_cpus: int) -> int:
    """Compute fixed panel height based on CPU count and terminal size."""
    return min(total_cpus + 5, shutil.get_terminal_size().lines - 3)
