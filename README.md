# pmap

Parallel map with beautiful progress bars for Python. Drop-in replacement for `map()` powered by [joblib](https://joblib.readthedocs.io/), with Rich progress bars in the terminal and tqdm widgets in Jupyter notebooks.

![pmap simple progress bar](screenshots/simple-bar.gif)

## Features

### Parallel execution with progress bars

One function call. Automatic parallelism. Live progress.

```python
from pmap import pmap

results = pmap(process, items, n_jobs=4)
```

### Per-job progress bars

See what each CPU core is doing in real-time with a Rich panel showing individual job progress and timing estimates.

```python
results = pmap(process, items, n_jobs=4, show_job_bars=True)
```

![Per-job progress bars](screenshots/job-bars.gif)

### Worker output routed above progress bars

`print()`, `rich.print()`, and `loguru.logger` output from worker processes appears cleanly above the progress bar — no garbled terminal output.

```python
from loguru import logger

def process(x):
    logger.info(f"Processing item {x}")
    return x ** 2

results = pmap(process, items, n_jobs=4)
```

![Loguru output routing](screenshots/loguru-output.gif)

### Safe mode

Catch exceptions per-item instead of crashing the entire job. Failed items return error dicts while successful items return normally.

```python
results = pmap(risky_fn, items, safe_mode=True)

# results[0] = 42                                                   (success)
# results[1] = {'error': '...', 'error_type': 'ValueError', ...}   (failure)
```

### DataFrame parallelism

Split a DataFrame into chunks, process in parallel, and reassemble — with optional group-aware splitting.

```python
from pmap import pmap_df

df = pmap_df(transform, df, n_chunks=100)
df = pmap_df(transform, df, groups="user_id")  # keep groups together
```

### Notebook auto-detection

Automatically switches to tqdm widgets in Jupyter notebooks (Rich Live doesn't support notebooks). ANSI codes from `rich.print()` are stripped automatically.

```python
# In a notebook — just works, no configuration needed
results = pmap(process, items, n_jobs=4)
```

### Thread and process flexibility

```python
# Use threads instead of processes (for I/O-bound work)
results = pmap(fetch, urls, n_jobs=8, prefer='threads')

# Use spawn context (for CUDA/macOS compatibility)
results = pmap(train, batches, n_jobs=4, spawn=True)
```

## Installation

```bash
# With uv
uv add git+https://github.com/vmasrani/pmap.git

# With pip
pip install git+https://github.com/vmasrani/pmap.git
```

## Quick Start

```python
import time
from pmap import pmap

def slow_square(x):
    time.sleep(0.5)
    return x ** 2

# Parallel with progress bar
results = pmap(slow_square, range(100), n_jobs=4)

# With per-job progress bars
results = pmap(slow_square, range(100), n_jobs=4, show_job_bars=True)

# With description
results = pmap(slow_square, range(100), n_jobs=4, desc="Squaring")
```

## API Reference

### `pmap(f, arr, **kwargs)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `f` | — | Function to apply to each element |
| `arr` | — | Iterable of elements to process |
| `n_jobs` | `-1` | Number of parallel jobs (`-1` = all CPUs, `1` = sequential) |
| `show_job_bars` | `False` | Show per-job progress bars with CPU panel |
| `backend` | `'auto'` | `'auto'`, `'rich'`, or `'tqdm'` |
| `prefer` | `None` | `'threads'` for threading backend |
| `safe_mode` | `False` | Return error dicts instead of raising |
| `spawn` | `False` | Use spawn multiprocessing context |
| `batch_size` | `'auto'` | Joblib batch size |
| `disable_tqdm` | `False` | Disable progress bar |
| `desc` | `'Processing'` | Progress bar description |

### `pmap_df(f, df, **kwargs)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `f` | — | Function to apply to each DataFrame chunk |
| `df` | — | DataFrame to split and process |
| `n_chunks` | `100` | Number of chunks to split into |
| `groups` | `None` | Column name for group-aware splitting |
| `axis` | `0` | Concatenation axis |

### `safe(f)`

Decorator that wraps a function to catch exceptions and return error dicts.

### `run_async(f)`

Decorator that runs a function in a background process, returning a `multiprocessing.Queue` for retrieving the result.

```python
from pmap import run_async

@run_async
def long_task(n):
    time.sleep(n)
    return "done"

queue = long_task(10)
result = queue.get()  # blocks until complete
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Parallelism | [joblib](https://joblib.readthedocs.io/) |
| Terminal progress | [Rich](https://rich.readthedocs.io/) |
| Notebook progress | [tqdm](https://tqdm.github.io/) |
| Logging | [loguru](https://loguru.readthedocs.io/) |
| DataFrame ops | [pandas](https://pandas.pydata.org/), [scikit-learn](https://scikit-learn.org/) (GroupKFold) |

## Recording the demo GIFs

The demo GIFs are generated with [VHS](https://github.com/charmbracelet/vhs):

```bash
brew install vhs
vhs demo/simple-bar.tape
vhs demo/job-bars.tape
vhs demo/loguru-output.tape
```

## License

MIT
