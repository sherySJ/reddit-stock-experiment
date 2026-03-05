#!/usr/bin/env python3
"""
Step 2: Extract all top-level comments from raw thread JSONs.

Two-phase approach:
  Phase 1 (extract):  Read raw threads → dump all top-level comments to all_comments.json
  Phase 2 (build):    Read AI-extracted tickers from recommendations.json → generate HTML

Usage:
  python 2_extract_tickers.py extract   # Phase 1: dump comments
  python 2_extract_tickers.py build     # Phase 2: build dashboard from AI results
"""

import json
import os
import sys
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_threads")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
ALL_COMMENTS_PATH = os.path.join(BASE_DIR, "data", "all_comments.json")
RECOMMENDATIONS_PATH = os.path.join(BASE_DIR, "data", "recommendations.json")
THREAD_INDEX_PATH = os.path.join(BASE_DIR, "data", "thread_index.json")


def phase_extract():
    """Extract all top-level comments from raw thread JSONs."""
    # Load thread index for metadata
    with open(THREAD_INDEX_PATH) as f:
        threads = json.load(f)
    thread_meta = {t["id"]: t for t in threads}

    all_comments = []
    files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json")]
    print(f"Reading {len(files)} raw thread files...\n")

    for fname in sorted(files):
        thread_id = fname.replace(".json", "")
        filepath = os.path.join(RAW_DIR, fname)

        try:
            with open(filepath) as f:
                data = json.load(f)

            meta = thread_meta.get(thread_id, {})
            thread_title = meta.get("title", "")

            # Extract top-level comments only
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
                    "body": body[:1000],  # cap at 1000 chars for AI processing
                })
        except Exception as e:
            print(f"  Error reading {fname}: {e}")

    # Save all comments
    with open(ALL_COMMENTS_PATH, "w") as f:
        json.dump(all_comments, f, indent=2)

    print(f"Extracted {len(all_comments)} top-level comments from {len(files)} threads")
    print(f"Saved to {ALL_COMMENTS_PATH}")
    print(f"\nNext: AI will extract tickers, then run 'python 2_extract_tickers.py build'")


def phase_build():
    """Build extraction dashboard from AI-extracted recommendations."""
    if not os.path.exists(RECOMMENDATIONS_PATH):
        print("Error: No recommendations.json found. AI extraction hasn't run yet.")
        sys.exit(1)

    with open(RECOMMENDATIONS_PATH) as f:
        recs = json.load(f)

    print(f"Loaded {len(recs)} recommendations")

    # Deduplicate: same author + same ticker → keep highest-upvoted
    seen = {}
    for r in recs:
        key = (r.get("author", ""), r.get("ticker", ""))
        if key not in seen or r.get("score", 0) > seen[key].get("score", 0):
            seen[key] = r
    deduped = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)
    print(f"After dedup: {len(deduped)} unique author+ticker recommendations")

    # Count tickers
    ticker_counts = {}
    for r in deduped:
        t = r.get("ticker", "")
        if t not in ticker_counts:
            ticker_counts[t] = {"count": 0, "total_score": 0, "recs": []}
        ticker_counts[t]["count"] += 1
        ticker_counts[t]["total_score"] += r.get("score", 0)
        ticker_counts[t]["recs"].append(r)

    # Sort by mention count
    top_tickers = sorted(ticker_counts.items(), key=lambda x: x[1]["count"], reverse=True)

    # Save deduped recommendations
    deduped_path = os.path.join(BASE_DIR, "data", "recommendations_deduped.json")
    with open(deduped_path, "w") as f:
        json.dump(deduped, f, indent=2)

    # Generate HTML
    generate_extraction_html(deduped, top_tickers)
    print(f"\nDone! {len(deduped)} recommendations, {len(top_tickers)} unique tickers")


def generate_extraction_html(recs, top_tickers):
    total_authors = len(set(r.get("author", "") for r in recs))

    # Top tickers table
    ticker_rows = ""
    for i, (ticker, info) in enumerate(top_tickers[:50]):
        avg_score = info["total_score"] / info["count"] if info["count"] > 0 else 0
        ticker_rows += f'''
        <tr>
          <td class="rank">#{i+1}</td>
          <td class="ticker">${ticker}</td>
          <td class="count">{info["count"]}</td>
          <td class="score">{avg_score:.0f}</td>
        </tr>'''

    # Recent recommendations table
    rec_rows = ""
    for i, r in enumerate(recs[:100]):
        body_escaped = (
            r.get("body", "")[:200]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", " ")
        )
        score_class = "positive" if r.get("score", 0) > 0 else "negative"
        rec_rows += f'''
        <tr>
          <td class="ticker">${r.get("ticker", "?")}</td>
          <td class="author">u/{r.get("author", "?")}</td>
          <td class="score {score_class}">{r.get("score", 0)}</td>
          <td class="body">{body_escaped}...</td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reddit Stock Experiment — Ticker Extraction</title>
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
    --purple-glow: rgba(180, 74, 255, 0.15);
    --purple-glow-strong: rgba(180, 74, 255, 0.3);
    --green: #4aff91;
    --red: #ff4a5e;
    --cyan: #4af0ff;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px; }}

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
    font-size: 48px;
    font-weight: 900;
    background: linear-gradient(135deg, #fff 0%, var(--purple-light) 50%, var(--purple) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 16px;
    line-height: 1.1;
  }}
  .hero p {{ font-size: 18px; color: var(--text-muted); max-width: 650px; margin: 0 auto; }}

  .pipeline {{
    display: flex; justify-content: center; gap: 0; margin: 0 0 48px; flex-wrap: wrap;
  }}
  .pipeline-step {{ display: flex; align-items: center; }}
  .pipeline-step .step {{
    padding: 10px 20px; border-radius: 10px; font-size: 13px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 1px;
    border: 1px solid var(--card-border); background: var(--card); color: var(--text-dim);
  }}
  .pipeline-step .step.done {{
    border-color: var(--green); background: rgba(74, 255, 145, 0.1); color: var(--green);
  }}
  .pipeline-step .step.active {{
    border-color: var(--purple); background: var(--purple-glow); color: var(--purple-light);
    box-shadow: 0 0 20px var(--purple-glow);
  }}
  .pipeline-step .arrow {{ color: var(--text-dim); font-size: 18px; padding: 0 8px; }}

  .stats-bar {{
    display: flex; justify-content: center; gap: 32px; margin: 48px 0 56px; flex-wrap: wrap;
  }}
  .stat-box {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 16px;
    padding: 28px 36px; text-align: center; min-width: 180px; position: relative; overflow: hidden;
    transition: all 0.3s ease;
  }}
  .stat-box::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--purple), transparent);
  }}
  .stat-box:hover {{
    border-color: var(--purple); box-shadow: 0 0 30px var(--purple-glow); transform: translateY(-2px);
  }}
  .stat-box .number {{
    font-size: 42px; font-weight: 900; color: var(--purple-light); line-height: 1; margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace;
  }}
  .stat-box .label {{
    font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;
  }}

  .section-header {{
    margin-bottom: 32px; padding-left: 16px; border-left: 3px solid var(--purple);
  }}
  .section-header h2 {{ font-size: 28px; font-weight: 800; margin-bottom: 4px; }}
  .section-header p {{ color: var(--text-muted); font-size: 15px; }}

  table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; }}
  th {{
    text-align: left; padding: 12px 16px; font-size: 11px; text-transform: uppercase;
    letter-spacing: 1.5px; color: var(--text-dim); font-weight: 700;
    border-bottom: 1px solid var(--card-border);
  }}
  td {{
    padding: 12px 16px; border-bottom: 1px solid rgba(30, 30, 53, 0.5); font-size: 14px;
    color: var(--text-muted);
  }}
  tr:hover td {{ background: var(--bg-subtle); }}
  .rank {{ color: var(--purple); font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .ticker {{ color: var(--cyan); font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .count {{ color: var(--text); font-weight: 600; font-family: 'JetBrains Mono', monospace; }}
  .score {{ font-family: 'JetBrains Mono', monospace; font-weight: 600; }}
  .score.positive {{ color: var(--green); }}
  .score.negative {{ color: var(--red); }}
  .author {{ color: var(--purple-light); font-weight: 500; font-size: 13px; }}
  .body {{ color: var(--text-dim); font-size: 13px; max-width: 500px; }}

  .footer {{ text-align: center; padding: 60px 0 40px; color: var(--text-dim); font-size: 13px; }}
</style>
</head>
<body>
<div class="container">

  <div class="hero">
    <div class="hero-badge">Step 2 — Ticker Extraction</div>
    <h1>Every Stock Mentioned on r/ValueInvesting</h1>
    <p>AI extracted every stock ticker from 6,457 comments — here's what Reddit was recommending in February 2025.</p>
  </div>

  <div class="pipeline">
    <div class="pipeline-step"><div class="step done">1. Scrape</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step active">2. Extract</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">3. AI Score</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">4. Backtest</div><div class="arrow">→</div></div>
    <div class="pipeline-step"><div class="step">5. Results</div></div>
  </div>

  <div class="stats-bar">
    <div class="stat-box">
      <div class="number">{len(recs):,}</div>
      <div class="label">Recommendations</div>
    </div>
    <div class="stat-box">
      <div class="number">{len(top_tickers)}</div>
      <div class="label">Unique Tickers</div>
    </div>
    <div class="stat-box">
      <div class="number">{total_authors}</div>
      <div class="label">Unique Authors</div>
    </div>
    <div class="stat-box">
      <div class="number">Feb 2025</div>
      <div class="label">Collection Window</div>
    </div>
  </div>

  <div class="section-header">
    <h2>Most Mentioned Stocks</h2>
    <p>Top 50 tickers by number of unique recommendations</p>
  </div>

  <table>
    <thead><tr><th>Rank</th><th>Ticker</th><th>Mentions</th><th>Avg Upvotes</th></tr></thead>
    <tbody>{ticker_rows}</tbody>
  </table>

  <div class="section-header">
    <h2>All Recommendations</h2>
    <p>Individual stock recommendations sorted by upvotes (showing top 100)</p>
  </div>

  <table>
    <thead><tr><th>Ticker</th><th>Author</th><th>Score</th><th>Comment</th></tr></thead>
    <tbody>{rec_rows}</tbody>
  </table>

  <div class="footer">
    <p>Extracted from r/ValueInvesting — February 2025</p>
  </div>

</div>
</body>
</html>'''

    output_path = os.path.join(RESULTS_DIR, "extraction_preview.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated preview: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("extract", "build"):
        print("Usage:")
        print("  python 2_extract_tickers.py extract   # Dump all comments")
        print("  python 2_extract_tickers.py build     # Build dashboard from AI results")
        sys.exit(1)

    if sys.argv[1] == "extract":
        phase_extract()
    elif sys.argv[1] == "build":
        phase_build()
