#!/usr/bin/env python3
"""
Measures dashboard page-load latency for Bank of FinTechCo.

Usage:
  python loadtest.py [--url URL] [--requests N] [--baseline-ms MS]

If p50 latency exceeds --baseline-ms, exits with code 1 and prints a
structured INCIDENT block so callers can act on it (e.g. Slack alert).
"""

import argparse
import json
import statistics
import sys
import time

import requests

DEFAULT_URL         = "http://localhost:8080"
DEFAULT_N           = 50
DEFAULT_BASELINE_MS = 50        # golden baseline — alert if p50 exceeds this
USERNAME            = "testuser"
PASSWORD            = "bankofanthos"


def login(base_url: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{base_url}/login", data={"username": USERNAME, "password": PASSWORD},
               allow_redirects=True, timeout=10)
    if "/home" not in r.url:
        raise RuntimeError(f"Login failed — landed on {r.url!r}")
    return s


def run(base_url: str, n: int) -> list[float]:
    session = login(base_url)
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        r = session.get(f"{base_url}/home", timeout=60)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            print(f"  [!] request {i+1}: HTTP {r.status_code}")
        latencies.append(elapsed_ms)
        print(f"  req {i+1:>3}/{n}  {elapsed_ms:7.1f} ms")
    return latencies


def compute_stats(latencies: list[float], n: int) -> dict:
    total_s = sum(latencies) / 1000
    return {
        "requests" : n,
        "total_s"  : round(total_s, 2),
        "rps"      : round(n / total_s, 2),
        "min_ms"   : round(min(latencies), 1),
        "mean_ms"  : round(statistics.mean(latencies), 1),
        "p50_ms"   : round(statistics.median(latencies), 1),
        "p95_ms"   : round(statistics.quantiles(latencies, n=100)[94], 1),
        "p99_ms"   : round(statistics.quantiles(latencies, n=100)[98], 1),
        "max_ms"   : round(max(latencies), 1),
    }


def report(stats: dict, baseline_ms: float) -> bool:
    """Print summary table. Returns True if an incident was detected."""
    s = stats
    incident = s["p50_ms"] > baseline_ms

    col = 14
    print()
    print("=" * 40)
    print(f"  {'Requests':<{col}} {s['requests']}")
    print(f"  {'Total time':<{col}} {s['total_s']} s")
    print(f"  {'Req/sec':<{col}} {s['rps']}")
    print("-" * 40)
    print(f"  {'Min':<{col}} {s['min_ms']} ms")
    print(f"  {'Mean':<{col}} {s['mean_ms']} ms")
    print(f"  {'p50':<{col}} {s['p50_ms']} ms  {'<-- SLOW' if incident else ''}")
    print(f"  {'p95':<{col}} {s['p95_ms']} ms")
    print(f"  {'p99':<{col}} {s['p99_ms']} ms")
    print(f"  {'Max':<{col}} {s['max_ms']} ms")
    print(f"  {'Baseline':<{col}} {baseline_ms} ms")
    print("=" * 40)

    if incident:
        ratio = round(s["p50_ms"] / baseline_ms, 1)
        print()
        print("INCIDENT_DETECTED")
        print(json.dumps({
            "route"       : "/home",
            "p50_ms"      : s["p50_ms"],
            "baseline_ms" : baseline_ms,
            "ratio"       : ratio,
            "rps"         : s["rps"],
            "p95_ms"      : s["p95_ms"],
            "p99_ms"      : s["p99_ms"],
        }))

    return incident


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--requests", dest="n", type=int, default=DEFAULT_N)
    parser.add_argument("--baseline-ms", type=float, default=DEFAULT_BASELINE_MS,
                        help="Golden baseline p50 (ms). Alert if exceeded.")
    args = parser.parse_args()

    print(f"Target   : {args.url}/home")
    print(f"Sending  : {args.n} sequential requests as {USERNAME!r}")
    print(f"Baseline : {args.baseline_ms} ms p50")
    print()

    latencies = run(args.url, args.n)
    stats     = compute_stats(latencies, args.n)
    incident  = report(stats, args.baseline_ms)

    sys.exit(1 if incident else 0)


if __name__ == "__main__":
    main()
