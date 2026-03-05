#!/usr/bin/env python3
"""
Extract all top-level comments from September 2025 raw threads.
Outputs all_comments.json for AI ticker extraction.
"""
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw_threads")
POSTS_FILE = os.path.join(DATA_DIR, "all_sept_posts.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "all_comments.json")

# Load post metadata for thread titles
with open(POSTS_FILE) as f:
    all_posts = json.load(f)
posts_by_id = {p["id"]: p for p in all_posts}

all_comments = []
files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json")]
print(f"Reading {len(files)} raw thread files...")

for fname in sorted(files):
    thread_id = fname.replace(".json", "")
    filepath = os.path.join(RAW_DIR, fname)

    try:
        with open(filepath) as f:
            data = json.load(f)

        meta = posts_by_id.get(thread_id, {})
        thread_title = meta.get("title", "")

        # Extract top-level comments
        children = data[1]["data"]["children"]
        for child in children:
            if child["kind"] != "t1":
                continue
            c = child["data"]
            body = c.get("body", "").strip()
            if not body or body in ("[deleted]", "[removed]"):
                continue

            all_comments.append({
                "id": c.get("id", ""),
                "thread_id": thread_id,
                "thread_title": thread_title,
                "author": c.get("author", "[deleted]"),
                "score": c.get("score", 0),
                "body": body[:1000],  # cap at 1000 chars
            })
    except Exception as e:
        print(f"  Error reading {fname}: {e}")

# Save all comments
with open(OUTPUT_FILE, "w") as f:
    json.dump(all_comments, f, indent=2)

print(f"\nExtracted {len(all_comments)} top-level comments from {len(files)} threads")
print(f"Saved to {OUTPUT_FILE}")

# Stats
authors = set(c["author"] for c in all_comments)
print(f"Unique authors: {len(authors)}")
avg_score = sum(c["score"] for c in all_comments) / len(all_comments) if all_comments else 0
print(f"Average comment score: {avg_score:.1f}")
