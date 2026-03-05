#!/usr/bin/env python3
"""Fetch full Reddit threads with requests session, retry logic, and rate limit handling."""
import json
import os
import time
import sys
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
THREADS_DIR = os.path.join(DATA_DIR, "raw_threads")
IDS_FILE = os.path.join(DATA_DIR, "all_qualifying_ids.json")
DELAY = 3  # seconds between requests
MAX_RETRIES = 3

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

session = requests.Session()
session.headers.update({
    "User-Agent": "python:reddit-stock-experiment:v1.0",
})

with open(IDS_FILE) as f:
    thread_ids = json.load(f)

already = set(f.replace(".json", "") for f in os.listdir(THREADS_DIR) if f.endswith(".json"))
to_fetch = [tid for tid in thread_ids if tid not in already]
print(f"Total: {len(thread_ids)}, Already fetched: {len(already)}, Remaining: {len(to_fetch)}")
print(f"Estimated time: ~{len(to_fetch) * DELAY / 60:.0f} minutes", flush=True)

success = 0
failed = 0
failed_ids = []

for i, tid in enumerate(to_fetch):
    print(f"[{i+1}/{len(to_fetch)}] {tid}...", end=" ", flush=True)

    url = f"https://www.reddit.com/comments/{tid}.json?limit=500"
    ok = False
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"429 (wait {wait}s)", end=" ", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            out = os.path.join(THREADS_DIR, f"{tid}.json")
            with open(out, "w") as f:
                json.dump(data, f)
            success += 1
            ok = True
            print("OK", flush=True)
            break
        except requests.exceptions.Timeout:
            print(f"timeout(r{attempt+1})", end=" ", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"err({e})", end=" ", flush=True)
            time.sleep(5)

    if not ok:
        failed += 1
        failed_ids.append(tid)
        print("FAILED", flush=True)

    # Progress summary every 50
    if (i + 1) % 50 == 0:
        total_saved = len(already) + success
        print(f"--- Progress: {success} ok, {failed} failed, {total_saved} total saved ---", flush=True)

    time.sleep(DELAY)

total_saved = len([f for f in os.listdir(THREADS_DIR) if f.endswith(".json")])
print(f"\nDone! Success: {success}, Failed: {failed}, Total saved: {total_saved}")
if failed_ids:
    with open(os.path.join(DATA_DIR, "failed_thread_ids.json"), "w") as f:
        json.dump(failed_ids, f, indent=2)
    print(f"Failed IDs saved ({len(failed_ids)} total)")
