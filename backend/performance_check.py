"""Thirty-minute HTTP workload for NFR4.1 and NFR4.3."""
import argparse
import asyncio
import ctypes
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(.95 * len(ordered)) - 1] if ordered else 0.0


async def run(base_url: str, tokens: list[str], duration: int, report_path: Path):
    if len(tokens) != 20:
        raise ValueError("Exactly 20 distinct user tokens are required")
    samples: dict[str, list[float]] = {"search": [], "recommendation": []}
    statuses: Counter[str] = Counter()
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    deadline = started + duration
    max_tick_gap = 0.0
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=20)
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
            async def worker(index: int, token: str):
                sequence = index % 2
                headers = {"Authorization": f"Bearer {token}"}
                while time.monotonic() < deadline:
                    kind = "search" if sequence % 2 == 0 else "recommendation"
                    path = "/movies?q=Performance" if kind == "search" else "/me/recommendations?k=10"
                    request_start = time.perf_counter()
                    try:
                        response = await client.get(path, headers=headers)
                        statuses[str(response.status_code)] += 1
                        if response.is_success:
                            samples[kind].append((time.perf_counter() - request_start) * 1000)
                    except httpx.HTTPError as error:
                        statuses[type(error).__name__] += 1
                    sequence += 1

            async def progress():
                nonlocal max_tick_gap
                last_tick = time.monotonic()
                last_report = last_tick
                while time.monotonic() < deadline:
                    await asyncio.sleep(min(10, max(0, deadline - time.monotonic())))
                    current = time.monotonic()
                    max_tick_gap = max(max_tick_gap, current - last_tick)
                    last_tick = current
                    if current - last_report >= 60 or current >= deadline:
                        last_report = current
                        elapsed = int(current - started)
                        failures = sum(value for code, value in statuses.items() if code != "200")
                        print(f"progress elapsed_s={elapsed} search={len(samples['search'])} recommendation={len(samples['recommendation'])} failures={failures} max_gap_s={max_tick_gap:.1f}", flush=True)

            await asyncio.gather(progress(), *(worker(index, token) for index, token in enumerate(tokens)))
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    total = sum(statuses.values())
    server_errors = sum(value for code, value in statuses.items() if code.isdigit() and int(code) >= 500)
    connection_errors = sum(value for code, value in statuses.items() if not code.isdigit())
    report = {
        "started_at_utc": started_at.isoformat(),
        "duration_seconds": round(time.monotonic() - started, 2),
        "wall_duration_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 2),
        "max_progress_gap_seconds": round(max_tick_gap, 2),
        "virtual_users": 20,
        "total_requests": total,
        "statuses": dict(statuses),
        "search_success": len(samples["search"]),
        "recommendation_success": len(samples["recommendation"]),
        "search_p95_ms": round(p95(samples["search"]), 2),
        "recommendation_p95_ms": round(p95(samples["recommendation"]), 2),
        "server_error_rate_percent": round(100 * server_errors / total, 4) if total else None,
        "connection_errors": connection_errors,
        "minimum_samples_met": min(len(samples["search"]), len(samples["recommendation"])) >= 1000,
    }
    report["continuous_30min"] = report["duration_seconds"] >= 1800 and report["max_progress_gap_seconds"] < 120 and abs(report["wall_duration_seconds"] - report["duration_seconds"]) < 120
    report["search_target_met"] = report["minimum_samples_met"] and report["search_p95_ms"] <= 800
    report["recommendation_target_met"] = report["minimum_samples_met"] and report["recommendation_p95_ms"] <= 1200
    report["server_error_target_met"] = report["server_error_rate_percent"] is not None and report["server_error_rate_percent"] < 1
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--tokens-file", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, json.loads(args.tokens_file.read_text(encoding="utf-8")), args.duration, args.report))
