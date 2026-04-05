#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["parmap", "tqdm"]
# ///
"""Benchmark: parmap — simple parallel map with optional tqdm.

Workload: Monte Carlo European call option pricing (Black-Scholes path simulation).
Each task runs 50k simulations of 200 daily steps. 80 tasks ≈ 30s on 8 cores.
"""
import math
import random
import time
import parmap


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
    seeds = list(range(N_TASKS))

    print("=" * 60)
    print("parmap — parmap.map with tqdm progress bar")
    print("=" * 60)
    t0 = time.perf_counter()
    results = parmap.map(price_option, seeds, pm_pbar=True, pm_processes=8)
    elapsed = time.perf_counter() - t0
    avg = sum(r["price"] for r in results) / len(results)
    print(f"{len(results)} options priced in {elapsed:.1f}s  (avg price: ${avg:.4f})")
