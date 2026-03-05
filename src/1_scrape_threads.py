#!/usr/bin/env python3
"""
Step 1: Scrape stock recommendation threads from r/ValueInvesting (Feb 2025).

Two-phase approach:
  Phase 1 (fetch):  Pull ALL Feb 2025 posts via Pullpush archive → all_feb_posts.json
  Phase 2 (build):  Read AI-classified qualifying IDs → fetch full threads from Reddit → HTML

Usage:
  python 1_scrape_threads.py fetch    # Phase 1: download all posts
  python 1_scrape_threads.py build    # Phase 2: fetch threads + generate HTML
"""

import json
import os
import sys
import time
import datetime
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_threads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
ALL_POSTS_PATH = os.path.join(BASE_DIR, "data", "all_feb_posts.json")
QUALIFYING_IDS_PATH = os.path.join(BASE_DIR, "data", "qualifying_ids.json")
THREAD_INDEX_PATH = os.path.join(BASE_DIR, "data", "thread_index.json")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "python:reddit-stock-experiment:v1.0",
})

FEB_START = datetime.datetime(2025, 2, 1, tzinfo=datetime.timezone.utc)
FEB_END = datetime.datetime(2025, 2, 28, 23, 59, 59, tzinfo=datetime.timezone.utc)


# ── Phase 1: Fetch all posts from Pullpush ──────────────────────────

def pullpush_search(after_ts):
    feb_end_ts = int(FEB_END.timestamp())
    resp = session.get("https://api.pullpush.io/reddit/search/submission/", params={
        "subreddit": "ValueInvesting",
        "after": after_ts,
        "before": feb_end_ts,
        "size": 100,
        "sort": "asc",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def phase_fetch():
    print("Phase 1: Fetching ALL r/ValueInvesting posts from Feb 2025...\n")

    all_posts = []
    after_ts = int(FEB_START.timestamp())
    page = 0

    while True:
        page += 1
        try:
            posts = pullpush_search(after_ts)
        except Exception as e:
            print(f"  Page {page}: Error: {e}")
            time.sleep(3)
            continue

        if not posts:
            break

        all_posts.extend(posts)
        after_ts = int(posts[-1]["created_utc"])

        date_str = datetime.datetime.fromtimestamp(
            after_ts, tz=datetime.timezone.utc
        ).strftime("%b %d")
        print(f"  Page {page}: {len(posts)} posts (total: {len(all_posts)}, through {date_str})")

        if len(posts) < 100:
            break

        time.sleep(0.5)

    # Save all posts
    with open(ALL_POSTS_PATH, "w") as f:
        json.dump(all_posts, f, indent=2)

    print(f"\nDone! {len(all_posts)} posts saved to {ALL_POSTS_PATH}")
    print(f"\nNext: AI will classify these posts, then run 'python 1_scrape_threads.py build'")


# ── Phase 2: Fetch full threads + generate HTML ─────────────────────

def fetch_thread(permalink, max_retries=3):
    url = f"https://www.reddit.com{permalink}.json?limit=500"
    for attempt in range(max_retries):
        resp = session.get(url, timeout=30)
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"    Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()  # raise on final failure


def count_top_comments(children):
    return sum(1 for child in children if child["kind"] == "t1")


def extract_top_comments(children, limit=8):
    comments = []
    for child in children:
        if child["kind"] != "t1":
            continue
        c = child["data"]
        comments.append({
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": c.get("body", "")[:500],
        })
    comments.sort(key=lambda x: x["score"], reverse=True)
    return comments[:limit]


def phase_build():
    # Load all posts
    if not os.path.exists(ALL_POSTS_PATH):
        print("Error: Run 'python 1_scrape_threads.py fetch' first.")
        sys.exit(1)

    with open(ALL_POSTS_PATH) as f:
        all_posts = json.load(f)
    posts_by_id = {p["id"]: p for p in all_posts}

    # Load qualifying IDs (from AI classification)
    if not os.path.exists(QUALIFYING_IDS_PATH):
        print("Error: No qualifying_ids.json found. AI classification hasn't run yet.")
        sys.exit(1)

    with open(QUALIFYING_IDS_PATH) as f:
        qualifying_ids = json.load(f)
    print(f"Qualifying threads: {len(qualifying_ids)} / {len(all_posts)} total posts\n")

    # Load cache
    cache = {}
    if os.path.exists(THREAD_INDEX_PATH):
        with open(THREAD_INDEX_PATH) as f:
            cache = {t["id"]: t for t in json.load(f)}

    # Fetch full threads
    full_threads = []
    for i, post_id in enumerate(qualifying_ids):
        p = posts_by_id.get(post_id)
        if not p:
            print(f"  [{i+1}/{len(qualifying_ids)}] Warning: ID {post_id} not found in posts")
            continue

        if post_id in cache:
            full_threads.append(cache[post_id])
            print(f"  [{i+1}/{len(qualifying_ids)}] Cached: {p['title'][:60]}...")
            continue

        print(f"  [{i+1}/{len(qualifying_ids)}] Fetching: {p['title'][:60]}...")
        permalink = p.get("permalink", f"/r/ValueInvesting/comments/{post_id}/")
        try:
            data = fetch_thread(permalink)
            filepath = os.path.join(RAW_DIR, f"{post_id}.json")
            with open(filepath, "w") as f:
                json.dump(data, f)

            thread = {
                "id": post_id,
                "title": p.get("title", ""),
                "author": p.get("author", "[deleted]"),
                "score": p.get("score", 0),
                "upvote_ratio": p.get("upvote_ratio", 0),
                "num_comments": p.get("num_comments", 0),
                "permalink": permalink,
                "created_utc": p.get("created_utc", 0),
                "selftext": p.get("selftext", "")[:1000],
                "actual_comments": count_top_comments(data[1]["data"]["children"]),
                "top_comments": extract_top_comments(data[1]["data"]["children"]),
            }
            full_threads.append(thread)
            print(f"    -> {thread['actual_comments']} top-level comments")

        except Exception as e:
            print(f"    Error: {e}")

        time.sleep(2.5)  # slower to avoid rate limits

    # Sort by comment count
    full_threads.sort(key=lambda x: x.get("actual_comments", x["num_comments"]), reverse=True)

    # Save thread index
    with open(THREAD_INDEX_PATH, "w") as f:
        json.dump(full_threads, f, indent=2)
    print(f"\nSaved {len(full_threads)} threads to {THREAD_INDEX_PATH}")

    # Generate HTML
    generate_preview_html(full_threads)
    print(f"Done! {len(full_threads)} threads scraped and visualized.")


# ── HTML Generation ──────────────────────────────────────────────────

def generate_preview_html(threads):
    total_comments = sum(t.get("actual_comments", t["num_comments"]) for t in threads)

    thread_cards = ""
    for i, t in enumerate(threads):
        created = datetime.datetime.fromtimestamp(t["created_utc"], tz=datetime.timezone.utc)
        date_str = created.strftime("%b %d, %Y")
        comments_count = t.get("actual_comments", t["num_comments"])

        comments_html = ""
        for c in t.get("top_comments", []):
            body_escaped = (
                c["body"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            score_class = "positive" if c["score"] > 0 else "negative"
            comments_html += f'''
            <div class="comment">
              <div class="comment-header">
                <span class="comment-author">u/{c["author"]}</span>
                <span class="comment-score {score_class}">{c["score"]} pts</span>
              </div>
              <div class="comment-body">{body_escaped}</div>
            </div>'''

        selftext = (
            t.get("selftext", "")[:300]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        if len(t.get("selftext", "")) > 300:
            selftext += "..."

        thread_cards += f'''
        <div class="thread-card" style="animation-delay: {i * 0.08}s">
          <div class="thread-header">
            <div class="thread-rank">#{i + 1}</div>
            <div class="thread-meta">
              <h3 class="thread-title">{t["title"]}</h3>
              <div class="thread-info">
                <span class="thread-author">u/{t["author"]}</span>
                <span class="thread-date">{date_str}</span>
              </div>
            </div>
          </div>
          <div class="thread-stats">
            <div class="stat-pill">
              <span class="stat-icon">▲</span>
              <span class="stat-value">{t["score"]}</span>
              <span class="stat-label">upvotes</span>
            </div>
            <div class="stat-pill">
              <span class="stat-icon">💬</span>
              <span class="stat-value">{comments_count}</span>
              <span class="stat-label">comments</span>
            </div>
            <div class="stat-pill">
              <span class="stat-icon">⬆</span>
              <span class="stat-value">{int(t.get("upvote_ratio", 0) * 100)}%</span>
              <span class="stat-label">upvoted</span>
            </div>
          </div>
          {"<div class='thread-body'>" + selftext + "</div>" if selftext else ""}
          <div class="comments-section">
            <div class="comments-label">Top Comments</div>
            {comments_html}
          </div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reddit Stock Experiment — Scraped Threads</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {{
    --bg: #08080f;
    --bg-subtle: #0d0d18;
    --card: #12121f;
    --card-hover: #18182a;
    --card-border: #1e1e35;
    --text: #e8e8f0;
    --text-muted: #8888a8;
    --text-dim: #555570;
    --purple: #b44aff;
    --purple-light: #c77dff;
    --purple-dark: #7b2fbe;
    --purple-glow: rgba(180, 74, 255, 0.15);
    --purple-glow-strong: rgba(180, 74, 255, 0.3);
    --pink: #ff4a8d;
    --cyan: #4af0ff;
    --green: #4aff91;
    --red: #ff4a5e;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    overflow-x: hidden;
  }}

  .container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 24px;
  }}

  .hero {{
    text-align: center;
    padding: 80px 0 60px;
    position: relative;
  }}
  .hero::before {{
    content: '';
    position: absolute;
    top: -150px; left: 50%; transform: translateX(-50%);
    width: 800px; height: 800px;
    background: radial-gradient(circle, var(--purple-glow) 0%, transparent 60%);
    pointer-events: none;
  }}
  .hero-badge {{
    display: inline-block;
    padding: 6px 18px;
    border: 1px solid var(--purple);
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    color: var(--purple-light);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 24px;
    background: var(--purple-glow);
    box-shadow: 0 0 20px var(--purple-glow);
  }}
  .hero h1 {{
    font-size: 52px;
    font-weight: 900;
    background: linear-gradient(135deg, #fff 0%, var(--purple-light) 50%, var(--purple) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 16px;
    line-height: 1.1;
  }}
  .hero p {{
    font-size: 18px;
    color: var(--text-muted);
    max-width: 650px;
    margin: 0 auto;
    line-height: 1.7;
  }}

  .stats-bar {{
    display: flex;
    justify-content: center;
    gap: 32px;
    margin: 48px 0 56px;
    flex-wrap: wrap;
  }}
  .stat-box {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 28px 36px;
    text-align: center;
    min-width: 180px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
  }}
  .stat-box::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--purple), transparent);
  }}
  .stat-box:hover {{
    border-color: var(--purple);
    box-shadow: 0 0 30px var(--purple-glow);
    transform: translateY(-2px);
  }}
  .stat-box .number {{
    font-size: 42px;
    font-weight: 900;
    color: var(--purple-light);
    line-height: 1;
    margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace;
  }}
  .stat-box .label {{
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
  }}

  .section-header {{
    margin-bottom: 32px;
    padding-left: 16px;
    border-left: 3px solid var(--purple);
  }}
  .section-header h2 {{
    font-size: 28px;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 4px;
  }}
  .section-header p {{
    color: var(--text-muted);
    font-size: 15px;
  }}

  .thread-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 20px;
    transition: all 0.3s ease;
    animation: fadeInUp 0.5s ease forwards;
    opacity: 0;
    transform: translateY(20px);
  }}
  @keyframes fadeInUp {{
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .thread-card:hover {{
    border-color: rgba(180, 74, 255, 0.4);
    box-shadow: 0 4px 40px var(--purple-glow);
    background: var(--card-hover);
  }}
  .thread-header {{
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
  }}
  .thread-rank {{
    font-size: 14px;
    font-weight: 800;
    color: var(--purple);
    background: var(--purple-glow);
    padding: 6px 12px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    white-space: nowrap;
    border: 1px solid rgba(180, 74, 255, 0.2);
  }}
  .thread-title {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.3;
    margin-bottom: 6px;
  }}
  .thread-info {{
    display: flex;
    gap: 16px;
    font-size: 13px;
    color: var(--text-muted);
  }}
  .thread-author {{
    color: var(--purple-light);
    font-weight: 500;
  }}
  .thread-stats {{
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}
  .stat-pill {{
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-subtle);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    border: 1px solid var(--card-border);
  }}
  .stat-pill .stat-icon {{ font-size: 12px; }}
  .stat-pill .stat-value {{
    font-weight: 700;
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
  }}
  .stat-pill .stat-label {{ color: var(--text-dim); font-size: 11px; }}
  .thread-body {{
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 16px;
    padding: 12px 16px;
    background: var(--bg-subtle);
    border-radius: 10px;
    border-left: 3px solid var(--purple-glow-strong);
    line-height: 1.6;
  }}

  .comments-section {{
    border-top: 1px solid var(--card-border);
    padding-top: 16px;
  }}
  .comments-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    font-weight: 700;
    margin-bottom: 12px;
  }}
  .comment {{
    padding: 10px 14px;
    margin-bottom: 8px;
    background: var(--bg-subtle);
    border-radius: 10px;
    border-left: 2px solid var(--card-border);
    transition: border-color 0.2s ease;
  }}
  .comment:hover {{ border-left-color: var(--purple); }}
  .comment-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }}
  .comment-author {{ font-size: 12px; font-weight: 600; color: var(--purple-light); }}
  .comment-score {{ font-size: 12px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .comment-score.positive {{ color: var(--green); }}
  .comment-score.negative {{ color: var(--red); }}
  .comment-body {{ font-size: 13px; color: var(--text-muted); line-height: 1.5; word-wrap: break-word; }}

  .footer {{ text-align: center; padding: 60px 0 40px; color: var(--text-dim); font-size: 13px; }}
  .footer a {{ color: var(--purple-light); text-decoration: none; }}

  .pipeline {{
    display: flex;
    justify-content: center;
    gap: 0;
    margin: 0 0 48px;
    flex-wrap: wrap;
  }}
  .pipeline-step {{ display: flex; align-items: center; gap: 0; }}
  .pipeline-step .step {{
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    border: 1px solid var(--card-border);
    background: var(--card);
    color: var(--text-dim);
    transition: all 0.3s ease;
  }}
  .pipeline-step .step.active {{
    border-color: var(--purple);
    background: var(--purple-glow);
    color: var(--purple-light);
    box-shadow: 0 0 20px var(--purple-glow);
  }}
  .pipeline-step .arrow {{ color: var(--text-dim); font-size: 18px; padding: 0 8px; }}
</style>
</head>
<body>

<div class="container">

  <div class="hero">
    <div class="hero-badge">Step 1 — Data Collection</div>
    <h1>What If AI Read Every Stock Tip on Reddit?</h1>
    <p>Scraping every stock recommendation from r/ValueInvesting in February 2025 — here's what we found.</p>
  </div>

  <div class="pipeline">
    <div class="pipeline-step"><div class="step active">1. Scrape</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">2. Extract</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">3. AI Score</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">4. Backtest</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">5. Results</div></div>
  </div>

  <div class="stats-bar">
    <div class="stat-box">
      <div class="number">{len(threads)}</div>
      <div class="label">Threads Scraped</div>
    </div>
    <div class="stat-box">
      <div class="number">{total_comments:,}</div>
      <div class="label">Top-Level Comments</div>
    </div>
    <div class="stat-box">
      <div class="number">Feb 2025</div>
      <div class="label">Collection Window</div>
    </div>
    <div class="stat-box">
      <div class="number">r/ValueInvesting</div>
      <div class="label">Source</div>
    </div>
  </div>

  <div class="section-header">
    <h2>Scraped Threads</h2>
    <p>AI-filtered recommendation threads from r/ValueInvesting, February 2025, sorted by activity</p>
  </div>

  {thread_cards}

  <div class="footer">
    <p>Data scraped from r/ValueInvesting — February 2025</p>
    <p style="margin-top: 8px;">Part of the "What If AI Read Every Stock Tip on Reddit?" experiment</p>
  </div>

</div>

</body>
</html>'''

    output_path = os.path.join(RESULTS_DIR, "threads_preview.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated preview: {output_path}")


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "build"):
        print("Usage:")
        print("  python 1_scrape_threads.py fetch   # Download all Feb 2025 posts")
        print("  python 1_scrape_threads.py build   # Fetch threads + generate HTML")
        sys.exit(1)

    if sys.argv[1] == "fetch":
        phase_fetch()
    elif sys.argv[1] == "build":
        phase_build()
