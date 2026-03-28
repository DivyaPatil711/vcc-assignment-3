#!/usr/bin/env python3
"""
stress_test.py – Artificially loads the CPU/memory to trigger auto-scaling.
Run this to demo the 75% threshold trigger during the video recording.

Usage:
    python3 stress_test.py --cpu 80 --duration 120
"""

import argparse, multiprocessing, time, sys

def burn_cpu(stop_event):
    """Spin a tight loop to saturate one CPU core."""
    while not stop_event.is_set():
        _ = sum(i * i for i in range(10_000))

def main():
    parser = argparse.ArgumentParser(description="CPU stress test")
    parser.add_argument("--cpu",      type=int, default=80,
                        help="Target CPU % (default 80)")
    parser.add_argument("--duration", type=int, default=120,
                        help="Duration in seconds (default 120)")
    args = parser.parse_args()

    cores = multiprocessing.cpu_count()
    workers = max(1, int(cores * args.cpu / 100))
    print(f"Launching {workers} worker(s) on {cores} core(s) "
          f"for {args.duration}s to simulate ~{args.cpu}% CPU …")

    stop = multiprocessing.Event()
    procs = [multiprocessing.Process(target=burn_cpu, args=(stop,))
             for _ in range(workers)]
    for p in procs:
        p.start()

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        stop.set()
        for p in procs:
            p.join()
        print("Stress test finished.")

if __name__ == "__main__":
    main()
