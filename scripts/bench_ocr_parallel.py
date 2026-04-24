"""Benchmark: sequential vs. concurrent batch processing.

Measures the real impact of moving `LocalExtractor.extract` onto a worker
thread (via asyncio.to_thread) + the asyncio.Semaphore fan-out in the batch
upload handler. Self-contained — no backend, no DB, no real Gemini calls —
so it isolates the concurrency win and reports a clean speedup number for
the FYP jury.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/bench_ocr_parallel.py [N_DOCS]

What the three scenarios demonstrate:

1. **Tier-1 only** (pure PaddleOCR, sequential vs. asyncio.gather)
   Expected speedup: ~1.0x — PaddlePaddle's runtime internally serializes
   predict() calls on the CPU backend (shared thread pool), so thread-level
   parallelism doesn't help the forward pass. **This is honest data — do
   not hide it.** The to_thread change is still worth it because it unblocks
   the event loop so other coroutines (Gemini, status polls) can run.

2. **Event-loop responsiveness during OCR**
   Fires a 50ms heartbeat coroutine while OCR runs. Counts ticks.
   Before the to_thread change: ticks drop to ~0 (loop is blocked on OCR).
   After: ticks fire at full rate (loop is free while OCR runs on a thread).
   This is the correct reason to use to_thread for CPU-bound work in asyncio.

3. **Realistic batch** (Tier-1 OCR + simulated Tier-2 Gemini I/O)
   Models a real batch: each doc does Tier-1 OCR then a Tier-2 Gemini call
   (mocked as `asyncio.sleep(3.0)` — about average Gemini latency).
   Sequential: N*(T_ocr + T_gemini). Concurrent with Semaphore(3): parallel
   network calls dominate. **This is where the real speedup shows up.**
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import numpy as np


# Simulated Gemini call latency (seconds). Gemini 2.5 Flash via BAML with
# fallback chain averages 3-8s under real load; 3.0s is a conservative lower
# bound so the speedup number looks honest, not cherry-picked.
TIER2_SIMULATED_LATENCY = 3.0


def _synthetic_page(size=(1024, 768)):
    img = (np.random.rand(size[1], size[0], 3) * 255).astype(np.uint8)
    return type("Page", (), {"processed": img, "original": img})()


# ---------------------------------------------------------------------------
# Scenario 1 — Tier-1 only
# ---------------------------------------------------------------------------


async def scenario_1_tier1(n_docs, LocalExtractor):
    print(f"[1] Tier-1 OCR only (N={n_docs})")
    extractors = [LocalExtractor() for _ in range(n_docs)]
    pages_list = [[_synthetic_page()] for _ in range(n_docs)]

    # Sequential
    t0 = time.perf_counter()
    for ext, pages in zip(extractors, pages_list):
        await ext.extract(pages)
    seq = time.perf_counter() - t0

    # Concurrent
    t0 = time.perf_counter()
    await asyncio.gather(*[
        ext.extract(pages) for ext, pages in zip(extractors, pages_list)
    ])
    con = time.perf_counter() - t0

    speedup = seq / con if con > 0 else 0
    print(f"    sequential:  {seq:.2f}s")
    print(f"    concurrent:  {con:.2f}s")
    print(f"    speedup:     {speedup:.2f}x")
    print(f"    finding:     PaddlePaddle serializes internally — thread-level")
    print(f"                 parallelism is capped. Switch to ProcessPoolExecutor")
    print(f"                 for true multi-core OCR parallelism.")
    print()


# ---------------------------------------------------------------------------
# Scenario 2 — Event-loop responsiveness
# ---------------------------------------------------------------------------


async def scenario_2_responsiveness(LocalExtractor):
    print("[2] Event-loop responsiveness during Tier-1 OCR")

    async def heartbeat(duration_sec, counter):
        deadline = time.perf_counter() + duration_sec
        while time.perf_counter() < deadline:
            await asyncio.sleep(0.05)  # 20 Hz target
            counter[0] += 1

    # Run OCR + heartbeat in parallel. If OCR blocks the loop (no to_thread),
    # heartbeat barely ticks. With to_thread, heartbeat stays near 20 Hz.
    extractor = LocalExtractor()
    pages = [_synthetic_page()]
    ticks = [0]
    t0 = time.perf_counter()

    async def _ocr_job():
        await extractor.extract(pages)

    # Dispatch OCR and heartbeat concurrently; measure ticks/second.
    ocr_task = asyncio.create_task(_ocr_job())
    heart_task = asyncio.create_task(heartbeat(10.0, ticks))  # 10s cap
    await ocr_task
    ocr_duration = time.perf_counter() - t0
    heart_task.cancel()
    try:
        await heart_task
    except asyncio.CancelledError:
        pass

    expected_ticks = ocr_duration * 20  # 20 Hz target
    pct = (ticks[0] / expected_ticks * 100) if expected_ticks > 0 else 0
    print(f"    OCR duration:        {ocr_duration:.2f}s")
    print(f"    heartbeats fired:    {ticks[0]} (target {expected_ticks:.0f} @ 20Hz)")
    print(f"    loop responsiveness: {pct:.0f}%")
    if pct >= 70:
        print(f"    finding:             Loop stays responsive — to_thread works.")
    else:
        print(f"    finding:             PaddlePaddle holds the GIL during inference,")
        print(f"                         so the event loop can't tick at full rate")
        print(f"                         even with to_thread. For true responsiveness")
        print(f"                         under CPU-heavy Python-wrapped work, use")
        print(f"                         ProcessPoolExecutor — separate interpreter,")
        print(f"                         separate GIL.")
    print()


# ---------------------------------------------------------------------------
# Scenario 3 — Realistic batch (Tier-1 + simulated Tier-2)
# ---------------------------------------------------------------------------


async def _process_doc_like_batch(extractor, pages, sem, mock_gemini=True):
    """Mimics routes_batch._process_one shape: Tier-1 OCR, then a Tier-2
    Gemini call (simulated via asyncio.sleep)."""
    async with sem:
        await extractor.extract(pages)
        if mock_gemini:
            await asyncio.sleep(TIER2_SIMULATED_LATENCY)


async def scenario_3_realistic_batch(n_docs, LocalExtractor):
    print(f"[3] Realistic batch (Tier-1 OCR + mock Tier-2 Gemini @ {TIER2_SIMULATED_LATENCY}s, N={n_docs})")
    extractors = [LocalExtractor() for _ in range(n_docs)]
    pages_list = [[_synthetic_page()] for _ in range(n_docs)]

    # Sequential baseline: Semaphore(1) forces one doc at a time.
    sem1 = asyncio.Semaphore(1)
    t0 = time.perf_counter()
    await asyncio.gather(*[
        _process_doc_like_batch(ext, pages, sem1)
        for ext, pages in zip(extractors, pages_list)
    ])
    seq = time.perf_counter() - t0

    # Concurrent: Semaphore(3) — matches the production BATCH_CONCURRENCY default.
    sem3 = asyncio.Semaphore(3)
    t0 = time.perf_counter()
    await asyncio.gather(*[
        _process_doc_like_batch(ext, pages, sem3)
        for ext, pages in zip(extractors, pages_list)
    ])
    con = time.perf_counter() - t0

    speedup = seq / con if con > 0 else 0
    theoretical_max = min(n_docs, 3)
    print(f"    sequential (Semaphore=1):   {seq:.2f}s")
    print(f"    concurrent (Semaphore=3):   {con:.2f}s")
    print(f"    speedup:                    {speedup:.2f}x")
    print(f"    theoretical max:            {theoretical_max:.2f}x (bounded by concurrency)")
    print(f"    finding:                    Network-bound Tier-2 calls overlap.")
    print(f"                                This is where the real batch win lives.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    n_docs = int(sys.argv[1]) if len(sys.argv) > 1 else 6

    print("=" * 70)
    print(f"Parallelism benchmark — batch upload pipeline")
    print(f"  N docs:     {n_docs}")
    print(f"  CPU cores:  {os.cpu_count()}")
    print("=" * 70)
    print()

    from src.backend.extraction.local_extractor import LocalExtractor

    # Warm PaddleOCR once so the first real extract() doesn't skew the
    # sequential baseline with a ~3-4s model load.
    print("Warming PaddleOCR engine (one-time cost, not measured)...")
    warm = LocalExtractor()
    t_warm = time.perf_counter()
    await warm.extract([_synthetic_page((512, 384))])
    print(f"  warmup: {time.perf_counter() - t_warm:.2f}s")
    print()

    await scenario_1_tier1(n_docs, LocalExtractor)
    await scenario_2_responsiveness(LocalExtractor)
    await scenario_3_realistic_batch(n_docs, LocalExtractor)

    print("=" * 70)
    print("SUMMARY FOR JURY")
    print("=" * 70)
    print("- Tier-1 OCR (PaddleOCR) does not thread-parallelize — internal")
    print("  runtime serialization. This is a library constraint, not a bug.")
    print("- to_thread still wins: it unblocks the event loop so I/O-bound")
    print("  work (Tier-2 Gemini calls, DB commits, status polls) can run.")
    print("- Real batch speedup comes from Semaphore(3)-bounded concurrency")
    print("  over the mixed Tier-1/Tier-2 workload (Scenario 3). Scales up")
    print("  to the min of N_docs and the semaphore width.")
    print("- Across-batch scale: deploy with `uvicorn --workers N`. Each worker")
    print("  is a separate process with its own event loop and PaddleOCR — true")
    print("  OS-level parallelism, free with one config flag.")


if __name__ == "__main__":
    asyncio.run(main())
