#!/usr/bin/env python3
"""
Fetch full Reddit threads (post + all comments) for qualifying thread IDs.

Reads all_qualifying_ids.json and fetches each thread from Reddit's JSON API.
Saves each thread as a JSON file in data/raw_threads/{thread_id}.json.
Uses 2-second delay between requests to respect Reddit rate limits.
Skips threads that already have a saved file (resume capability).
"""
import json
import os
import time
import urllib.request
import urllib.error

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
THREADS_DIR = os.path.join(DATA_DIR, "raw_threads")
IDS_FILE = os.path.join(DATA_DIR, "all_qualifying_ids.json")
DELAY = 2  # seconds between requests
USER_AGENT = "Mozilla/5.0 (research project)"


def fetch_thread(thread_id):
    """Fetch a single thread from Reddit's JSON API."""
    url = f"https://www.reddit.com/comments/{thread_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code} for {thread_id}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"  URL error for {thread_id}: {e.reason}")
        return None
    except Exception as e:
        print(f"  Error for {thread_id}: {e}")
        return None


def main():
    # Load IDs
    with open(IDS_FILE) as f:
        thread_ids = json.load(f)

    total = len(thread_ids)
    print(f"Total qualifying threads: {total}")

    # Check which are already fetched
    already_fetched = set()
    for fname in os.listdir(THREADS_DIR):
        if fname.endswith(".json"):
            already_fetched.add(fname.replace(".json", ""))

    to_fetch = [tid for tid in thread_ids if tid not in already_fetched]
    print(f"Already fetched: {len(already_fetched)}")
    print(f"Remaining to fetch: {len(to_fetch)}")

    if not to_fetch:
        print("Nothing to fetch. All threads already downloaded.")
        return

    estimated_minutes = (len(to_fetch) * DELAY) / 60
    print(f"Estimated time: ~{estimated_minutes:.0f} minutes\n")

    success = 0
    failed = 0
    failed_ids = []

    for i, thread_id in enumerate(to_fetch):
        # Progress report every 10 threads
        if i > 0 and i % 10 == 0:
            elapsed_pct = (i / len(to_fetch)) * 100
            print(f"Progress: {i}/{len(to_fetch)} ({elapsed_pct:.1f}%) - "
                  f"success: {success}, failed: {failed}")

        data = fetch_thread(thread_id)

        if data is not None:
            output_path = os.path.join(THREADS_DIR, f"{thread_id}.json")
            with open(output_path, "w") as f:
                json.dump(data, f)
            success += 1
        else:
            failed += 1
            failed_ids.append(thread_id)

        # Rate limiting - skip delay on last item
        if i < len(to_fetch) - 1:
            time.sleep(DELAY)

    print(f"\nDone!")
    print(f"Successfully fetched: {success}")
    print(f"Failed: {failed}")
    if failed_ids:
        print(f"Failed IDs: {failed_ids}")
        # Save failed IDs for potential retry
        failed_path = os.path.join(DATA_DIR, "failed_thread_ids.json")
        with open(failed_path, "w") as f:
            json.dump(failed_ids, f, indent=2)
        print(f"Failed IDs saved to {failed_path}")

    # Final count
    total_saved = len([f for f in os.listdir(THREADS_DIR) if f.endswith(".json")])
    print(f"\nTotal threads saved in raw_threads/: {total_saved}")


if __name__ == "__main__":
    main()
