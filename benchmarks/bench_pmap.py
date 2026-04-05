#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pmap @ file:///Users/vmasrani/dev/sophia-opensource-projects/pmap"]
# ///
"""Benchmark: pmap — parallel map with Rich progress bars and clean output routing.

Workload: Monte Carlo European call option pricing (Black-Scholes path simulation).
Each task runs 50k simulations of 200 daily steps. 80 tasks ≈ 30s on 8 cores.
"""
import math
import random
import time


N_TASKS = 80
N_SIMS = 50_000
N_STEPS = 200


def price_option(seed: int) -> dict:
    """Price a European call option via Monte Carlo simulation."""
    rng = random.Random(seed)
    S0, K, T, r, sigma = 100.0, 105.0, 1.0, 0.05, 0.2
    dt = T / N_STEPS
    payoff_sum = 0.0
    for _ in range(N_SIMS):
        S = S0
        for _ in range(N_STEPS):
            S *= math.exp((r - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * rng.gauss(0, 1))
        payoff_sum += max(S - K, 0.0)
    price = math.exp(-r * T) * payoff_sum / N_SIMS
    if seed % 30 == 0:
        print(f"[seed={seed}] option price = ${price:.4f}")
    return {"seed": seed, "price": price}


if __name__ == "__main__":
    from pmap import pmap

    seeds = list(range(N_TASKS))

    # --- Run 1: simple progress bar ---
    print("=" * 60)
    print("pmap — simple progress bar")
    print("=" * 60)
    t0 = time.perf_counter()
    results = pmap(price_option, seeds, desc="MC pricing")
    elapsed = time.perf_counter() - t0
    avg = sum(r["price"] for r in results) / len(results)
    print(f"{len(results)} options priced in {elapsed:.1f}s  (avg price: ${avg:.4f})\n")

    # --- Run 2: per-job progress bars ---
    print("=" * 60)
    print("pmap — per-job progress bars (show_job_bars=True)")
    print("=" * 60)
    t0 = time.perf_counter()
    results = pmap(price_option, seeds, show_job_bars=True, desc="MC pricing")
    elapsed = time.perf_counter() - t0
    avg = sum(r["price"] for r in results) / len(results)
    print(f"{len(results)} options priced in {elapsed:.1f}s  (avg price: ${avg:.4f})\n")

    # --- Run 3: safe mode ---
    print("=" * 60)
    print("pmap — safe mode (per-item exception catching)")
    print("=" * 60)

    def flaky_price(seed):
        if seed == 60:
            raise ValueError(f"Bad market data for seed {seed}")
        return price_option(seed)

    t0 = time.perf_counter()
    results = pmap(flaky_price, seeds, safe_mode=True, desc="MC safe")
    elapsed = time.perf_counter() - t0
    errors = [r for r in results if isinstance(r, dict) and "error" in r]
    print(f"{len(results)} tasks ({len(errors)} errors caught) in {elapsed:.1f}s")
