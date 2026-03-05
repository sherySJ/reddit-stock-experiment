#!/usr/bin/env python3
"""Merge all qualifying ID files into one deduplicated list."""
import json
import glob
import os

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
files = sorted(glob.glob(os.path.join(data_dir, "qualifying_ids_*.json")))

all_ids = []
for f in files:
    with open(f) as fh:
        ids = json.load(fh)
        print(f"  {os.path.basename(f)}: {len(ids)} IDs")
        all_ids.extend(ids)

print(f"\nTotal before dedup: {len(all_ids)}")

# Deduplicate while preserving order
seen = set()
unique_ids = []
for id_ in all_ids:
    if id_ not in seen:
        seen.add(id_)
        unique_ids.append(id_)

print(f"Total after dedup:  {len(unique_ids)}")
print(f"Duplicates removed: {len(all_ids) - len(unique_ids)}")

output_path = os.path.join(data_dir, "all_qualifying_ids.json")
with open(output_path, "w") as fh:
    json.dump(unique_ids, fh, indent=2)

print(f"\nSaved to {output_path}")
