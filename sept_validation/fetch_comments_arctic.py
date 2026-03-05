#!/usr/bin/env python3
"""
Fetch all comments for qualifying threads using Arctic Shift API.
Much faster and more reliable than Reddit's JSON API.
"""
import json
import os
import time
import sys
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
THREADS_DIR = os.path.join(DATA_DIR, "raw_threads")
IDS_FILE = os.path.join(DATA_DIR, "all_qualifying_ids.json")
POSTS_FILE = os.path.join(DATA_DIR, "all_sept_posts.json")
DELAY = 0.5  # Arctic Shift is more lenient

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

session = requests.Session()
session.headers.update({
    "User-Agent": "python:reddit-stock-experiment:v1.0",
})

# Load qualifying IDs
with open(IDS_FILE) as f:
    thread_ids = json.load(f)

# Load post metadata for titles etc
with open(POSTS_FILE) as f:
    all_posts = json.load(f)
posts_by_id = {p["id"]: p for p in all_posts}

# Check what's already fetched
already = set(f.replace(".json", "") for f in os.listdir(THREADS_DIR) if f.endswith(".json"))
to_fetch = [tid for tid in thread_ids if tid not in already]
print(f"Total: {len(thread_ids)}, Already fetched: {len(already)}, Remaining: {len(to_fetch)}")
print(f"Estimated time: ~{len(to_fetch) * DELAY / 60:.1f} minutes", flush=True)

success = 0
failed = 0
failed_ids = []

for i, tid in enumerate(to_fetch):
    print(f"[{i+1}/{len(to_fetch)}] {tid}...", end=" ", flush=True)

    # Fetch comments from Arctic Shift
    url = "https://arctic-shift.photon-reddit.com/api/comments/search"
    params = {
        "link_id": tid,
        "limit": 100,
        "sort": "desc",
    }

    try:
        resp = session.get(url, params=params, timeout=20)
        if resp.status_code == 429:
            print("429, waiting 10s...", end=" ", flush=True)
            time.sleep(10)
            resp = session.get(url, params=params, timeout=20)

        resp.raise_for_status()
        result = resp.json()
        comments = result.get("data", [])

        # Get post metadata
        post_meta = posts_by_id.get(tid, {})

        # Build a structure similar to Reddit's JSON format for compatibility
        # with the existing extraction pipeline
        post_data = {
            "kind": "t3",
            "data": {
                "id": tid,
                "title": post_meta.get("title", ""),
                "author": post_meta.get("author", "[deleted]"),
                "score": post_meta.get("score", 0),
                "upvote_ratio": post_meta.get("upvote_ratio", 0),
                "num_comments": post_meta.get("num_comments", 0),
                "selftext": post_meta.get("selftext", ""),
                "permalink": post_meta.get("permalink", f"/r/ValueInvesting/comments/{tid}/"),
                "created_utc": post_meta.get("created_utc", 0),
            }
        }

        # Convert Arctic Shift comments to Reddit JSON format
        comment_children = []
        for c in comments:
            # Only include top-level comments (parent_id starts with t3_)
            parent = c.get("parent_id", "")
            if not parent.startswith("t3_"):
                continue
            comment_children.append({
                "kind": "t1",
                "data": {
                    "id": c.get("id", ""),
                    "author": c.get("author", "[deleted]"),
                    "score": c.get("score", 0),
                    "body": c.get("body", ""),
                    "created_utc": c.get("created_utc", 0),
                    "parent_id": parent,
                }
            })

        # Save in Reddit-compatible format
        thread_data = [
            {"data": {"children": [post_data]}},
            {"data": {"children": comment_children}}
        ]

        out = os.path.join(THREADS_DIR, f"{tid}.json")
        with open(out, "w") as f:
            json.dump(thread_data, f)

        success += 1
        print(f"OK ({len(comment_children)} comments)", flush=True)

    except Exception as e:
        failed += 1
        failed_ids.append(tid)
        print(f"FAILED ({e})", flush=True)

    # Progress summary every 100
    if (i + 1) % 100 == 0:
        total_saved = len(already) + success
        print(f"--- Progress: {success} ok, {failed} failed, {total_saved} total saved ---", flush=True)

    time.sleep(DELAY)

total_saved = len([f for f in os.listdir(THREADS_DIR) if f.endswith(".json")])
print(f"\nDone! Success: {success}, Failed: {failed}, Total saved: {total_saved}")
if failed_ids:
    with open(os.path.join(DATA_DIR, "failed_thread_ids.json"), "w") as f:
        json.dump(failed_ids, f, indent=2)
    print(f"Failed IDs saved ({len(failed_ids)} total)")
