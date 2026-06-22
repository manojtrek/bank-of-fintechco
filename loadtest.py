#!/usr/bin/env python3
"""
Measures dashboard page-load latency for Bank of FinTechCo.
Usage: python loadtest.py [--url http://localhost:8080] [--requests 50]
"""

import argparse
import statistics
import time

import requests

DEFAULT_URL = "http://localhost:8080"
DEFAULT_N   = 50
USERNAME    = "testuser"
PASSWORD    = "bankofanthos"


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


def report(latencies: list[float], n: int) -> None:
    total_s = sum(latencies) / 1000
    rps = n / total_s

    mn   = min(latencies)
    mean = statistics.mean(latencies)
    p50  = statistics.median(latencies)
    p95  = statistics.quantiles(latencies, n=100)[94]
    p99  = statistics.quantiles(latencies, n=100)[98]
    mx   = max(latencies)

    col = 14
    print()
    print("=" * 40)
    print(f"  {'Requests':<{col}} {n}")
    print(f"  {'Total time':<{col}} {total_s:.2f} s")
    print(f"  {'Req/sec':<{col}} {rps:.2f}")
    print("-" * 40)
    print(f"  {'Min':<{col}} {mn:.1f} ms")
    print(f"  {'Mean':<{col}} {mean:.1f} ms")
    print(f"  {'p50':<{col}} {p50:.1f} ms")
    print(f"  {'p95':<{col}} {p95:.1f} ms")
    print(f"  {'p99':<{col}} {p99:.1f} ms")
    print(f"  {'Max':<{col}} {mx:.1f} ms")
    print("=" * 40)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--requests", dest="n", type=int, default=DEFAULT_N)
    args = parser.parse_args()

    print(f"Target : {args.url}/home")
    print(f"Sending: {args.n} sequential requests as {USERNAME!r}")
    print()

    latencies = run(args.url, args.n)
    report(latencies, args.n)


if __name__ == "__main__":
    main()
