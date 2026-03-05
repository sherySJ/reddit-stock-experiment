#!/usr/bin/env python3
"""
Step 3: AI Reasoning Quality Scoring

Two-phase approach:
  Phase 1 (prepare): Read deduped recommendations → create scoring batches (comment text only, no ticker)
  Phase 2 (build):   Read AI scores → merge with recommendations → generate scoring dashboard HTML

Usage:
  python 3_score_reasoning.py prepare   # Phase 1: create blind scoring batches
  python 3_score_reasoning.py build     # Phase 2: merge scores + generate dashboard
"""

import json
import os
import sys
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
RECOMMENDATIONS_PATH = os.path.join(DATA_DIR, "recommendations_deduped.json")
SCORES_PATH = os.path.join(DATA_DIR, "scores.json")
SCORED_RECS_PATH = os.path.join(DATA_DIR, "recommendations_scored.json")

BATCH_SIZE = 25  # comments per scoring batch


def phase_prepare():
    """Create blind scoring batches — strip tickers, keep only comment text."""
    with open(RECOMMENDATIONS_PATH) as f:
        recs = json.load(f)

    print(f"Loaded {len(recs)} deduped recommendations")

    # Create blind items for scoring (no ticker, no reasoning summary)
    blind_items = []
    for r in recs:
        blind_items.append({
            "id": r["comment_id"] + "_" + r.get("ticker", "X"),
            "body": r.get("body", ""),
            "score": r.get("score", 0),  # Reddit upvotes — context only
        })

    # Split into batches
    num_batches = math.ceil(len(blind_items) / BATCH_SIZE)
    for i in range(num_batches):
        batch = blind_items[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        batch_path = os.path.join(DATA_DIR, f"scoring_batch_{i}.json")
        with open(batch_path, "w") as f:
            json.dump(batch, f, indent=2)

    print(f"Created {num_batches} scoring batches of ~{BATCH_SIZE} items each")
    print(f"Saved to data/scoring_batch_0.json through scoring_batch_{num_batches-1}.json")
    print(f"\nNext: AI scores each batch, then run 'python 3_score_reasoning.py build'")


def phase_build():
    """Merge AI scores with recommendations and generate dashboard."""
    if not os.path.exists(SCORES_PATH):
        print("Error: No scores.json found. AI scoring hasn't run yet.")
        sys.exit(1)

    with open(RECOMMENDATIONS_PATH) as f:
        recs = json.load(f)
    with open(SCORES_PATH) as f:
        scores = json.load(f)

    print(f"Loaded {len(recs)} recommendations and {len(scores)} scores")

    # Build score lookup by id
    score_lookup = {s["id"]: s for s in scores}

    # Merge scores into recommendations
    scored = []
    unscored = 0
    for r in recs:
        sid = r["comment_id"] + "_" + r.get("ticker", "X")
        s = score_lookup.get(sid, {})
        r["thesis_clarity"] = s.get("thesis_clarity", 0)
        r["risk_awareness"] = s.get("risk_awareness", 0)
        r["data_usage"] = s.get("data_usage", 0)
        r["specificity"] = s.get("specificity", 0)
        r["independent_thinking"] = s.get("independent_thinking", 0)
        dims = [r["thesis_clarity"], r["risk_awareness"], r["data_usage"],
                r["specificity"], r["independent_thinking"]]
        r["ai_score"] = round(sum(dims) / 5 * 10) if any(d > 0 for d in dims) else 0
        r["ai_explanation"] = s.get("explanation", "")
        if not any(d > 0 for d in dims):
            unscored += 1
        scored.append(r)

    # Save scored recommendations
    with open(SCORED_RECS_PATH, "w") as f:
        json.dump(scored, f, indent=2)

    print(f"Scored: {len(scored) - unscored}, Unscored: {unscored}")
    print(f"Saved to {SCORED_RECS_PATH}")

    # Generate dashboard
    generate_scoring_html(scored)


def generate_scoring_html(recs):
    """Generate the Step 3 scoring dashboard."""
    # Sort by AI score descending
    by_score = sorted(recs, key=lambda x: x.get("ai_score", 0), reverse=True)
    by_upvotes = sorted(recs, key=lambda x: x.get("score", 0), reverse=True)

    # Stats
    scored_recs = [r for r in recs if r.get("ai_score", 0) > 0]
    avg_score = sum(r["ai_score"] for r in scored_recs) / len(scored_recs) if scored_recs else 0
    high_quality = len([r for r in scored_recs if r["ai_score"] >= 60])
    low_quality = len([r for r in scored_recs if r["ai_score"] < 40])

    # Top 10 by AI score
    top_ai_rows = ""
    for i, r in enumerate(by_score[:20]):
        body_escaped = (
            r.get("body", "")[:250]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", " ")
        )
        explanation = (
            r.get("ai_explanation", "")[:200]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", " ")
        )
        top_ai_rows += f'''
        <tr>
          <td class="rank">#{i+1}</td>
          <td class="ticker">${r.get("ticker", "?")}</td>
          <td class="ai-score">{r.get("ai_score", 0)}</td>
          <td class="upvotes">{r.get("score", 0)}</td>
          <td class="body">{body_escaped}...</td>
        </tr>'''

    # Examples: highest-upvoted with low AI score vs low-upvoted with high AI score
    # Find a good "crowd miss" — high upvotes, low AI score
    crowd_misses = [r for r in by_upvotes[:50] if r.get("ai_score", 0) < 40 and r.get("ai_score", 0) > 0]
    # Find a good "hidden gem" — low upvotes, high AI score
    hidden_gems = [r for r in by_score[:50] if r.get("score", 0) <= 5]

    example_miss = crowd_misses[0] if crowd_misses else by_upvotes[0]
    example_gem = hidden_gems[0] if hidden_gems else by_score[0]

    def make_example_card(r, label, label_class):
        body = (r.get("body", "")[:400]
                .replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))
        explanation = (r.get("ai_explanation", "")[:300]
                      .replace("&", "&amp;").replace("<", "&lt;")
                      .replace(">", "&gt;").replace("\n", "<br>"))
        return f'''
        <div class="example-card {label_class}">
          <div class="example-label">{label}</div>
          <div class="example-meta">
            <span class="ticker">${r.get("ticker", "?")}</span>
            <span class="upvotes-badge">{r.get("score", 0)} upvotes</span>
            <span class="ai-badge">AI: {r.get("ai_score", 0)}/100</span>
          </div>
          <div class="example-body">{body}</div>
          <div class="example-dims">
            <span>Thesis: {r.get("thesis_clarity", 0)}</span>
            <span>Risk: {r.get("risk_awareness", 0)}</span>
            <span>Data: {r.get("data_usage", 0)}</span>
            <span>Specificity: {r.get("specificity", 0)}</span>
            <span>Independent: {r.get("independent_thinking", 0)}</span>
          </div>
          <div class="example-explanation">{explanation}</div>
        </div>'''

    miss_card = make_example_card(example_miss, "Popular but Weak Reasoning", "miss")
    gem_card = make_example_card(example_gem, "Buried but Strong Reasoning", "gem")

    # Score distribution histogram data
    buckets = [0] * 10  # 0-10, 10-20, ..., 90-100
    for r in scored_recs:
        idx = min(int(r["ai_score"] / 10), 9)
        buckets[idx] += 1

    # All recommendations table sorted by AI score
    all_rows = ""
    for i, r in enumerate(by_score[:100]):
        body_escaped = (
            r.get("body", "")[:200]
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\n", " ")
        )
        score_class = "high" if r.get("ai_score", 0) >= 60 else "mid" if r.get("ai_score", 0) >= 40 else "low"
        all_rows += f'''
        <tr>
          <td class="rank">#{i+1}</td>
          <td class="ticker">${r.get("ticker", "?")}</td>
          <td class="ai-score {score_class}">{r.get("ai_score", 0)}</td>
          <td class="score-dims">{r.get("thesis_clarity",0)}/{r.get("risk_awareness",0)}/{r.get("data_usage",0)}/{r.get("specificity",0)}/{r.get("independent_thinking",0)}</td>
          <td class="upvotes">{r.get("score", 0)}</td>
          <td class="body">{body_escaped}...</td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reddit Stock Experiment — AI Reasoning Scores</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
    --yellow: #ffd44a;
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

  .chart-container {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 16px;
    padding: 32px; margin-bottom: 56px;
  }}

  .examples-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 56px;
  }}
  @media (max-width: 800px) {{ .examples-grid {{ grid-template-columns: 1fr; }} }}

  .example-card {{
    background: var(--card); border: 1px solid var(--card-border); border-radius: 16px;
    padding: 24px; position: relative; overflow: hidden;
  }}
  .example-card.miss {{ border-color: var(--red); }}
  .example-card.miss .example-label {{ background: rgba(255, 74, 94, 0.15); color: var(--red); }}
  .example-card.gem {{ border-color: var(--green); }}
  .example-card.gem .example-label {{ background: rgba(74, 255, 145, 0.15); color: var(--green); }}

  .example-label {{
    display: inline-block; padding: 4px 12px; border-radius: 8px; font-size: 11px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px;
  }}
  .example-meta {{
    display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap;
  }}
  .example-meta .ticker {{ color: var(--cyan); font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 16px; }}
  .upvotes-badge {{
    background: rgba(255, 212, 74, 0.15); color: var(--yellow); padding: 2px 10px;
    border-radius: 6px; font-size: 12px; font-weight: 600; font-family: 'JetBrains Mono', monospace;
  }}
  .ai-badge {{
    background: var(--purple-glow); color: var(--purple-light); padding: 2px 10px;
    border-radius: 6px; font-size: 12px; font-weight: 600; font-family: 'JetBrains Mono', monospace;
  }}
  .example-body {{
    color: var(--text-muted); font-size: 14px; line-height: 1.6; margin-bottom: 12px;
    padding: 12px; background: var(--bg-subtle); border-radius: 8px;
  }}
  .example-dims {{
    display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;
  }}
  .example-dims span {{
    font-size: 11px; color: var(--text-dim); font-family: 'JetBrains Mono', monospace;
    background: var(--bg-subtle); padding: 2px 8px; border-radius: 4px;
  }}
  .example-explanation {{
    color: var(--text-dim); font-size: 13px; font-style: italic; padding-top: 8px;
    border-top: 1px solid var(--card-border);
  }}

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
  .ai-score {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 16px; }}
  .ai-score.high {{ color: var(--green); }}
  .ai-score.mid {{ color: var(--yellow); }}
  .ai-score.low {{ color: var(--red); }}
  .score-dims {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-dim); }}
  .upvotes {{ font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--yellow); }}
  .body {{ color: var(--text-dim); font-size: 13px; max-width: 400px; }}

  .footer {{ text-align: center; padding: 60px 0 40px; color: var(--text-dim); font-size: 13px; }}
</style>
</head>
<body>
<div class="container">

  <div class="hero">
    <div class="hero-badge">Step 3 — AI Reasoning Scores</div>
    <h1>Can AI Spot Good Reasoning?</h1>
    <p>Every recommendation scored blind — no ticker, no outcome — purely on the quality of the argument.</p>
  </div>

  <div class="pipeline">
    <div class="pipeline-step"><div class="step done">1. Scrape</div><div class="arrow">&rarr;</div></div>
    <div class="pipeline-step"><div class="step done">2. Extract</div><div class="arrow">&rarr;</div></div>
    <div class="pipeline-step"><div class="step active">3. AI Score</div><div class="arrow">&rarr;</div></div>
    <div class="pipeline-step"><div class="step">4. Backtest</div><div class="arrow">&rarr;</div></div>
    <div class="pipeline-step"><div class="step">5. Results</div></div>
  </div>

  <div class="stats-bar">
    <div class="stat-box">
      <div class="number">{len(scored_recs)}</div>
      <div class="label">Scored</div>
    </div>
    <div class="stat-box">
      <div class="number">{avg_score:.0f}</div>
      <div class="label">Avg AI Score</div>
    </div>
    <div class="stat-box">
      <div class="number">{high_quality}</div>
      <div class="label">High Quality (60+)</div>
    </div>
    <div class="stat-box">
      <div class="number">{low_quality}</div>
      <div class="label">Low Quality (&lt;40)</div>
    </div>
  </div>

  <div class="section-header">
    <h2>Score Distribution</h2>
    <p>How AI rated the reasoning quality across all {len(scored_recs)} recommendations</p>
  </div>

  <div class="chart-container">
    <canvas id="distChart" height="100"></canvas>
  </div>

  <div class="section-header">
    <h2>Upvotes vs Reasoning</h2>
    <p>Popular doesn't mean well-reasoned — and well-reasoned doesn't mean popular</p>
  </div>

  <div class="examples-grid">
    {miss_card}
    {gem_card}
  </div>

  <div class="section-header">
    <h2>Top 20 by AI Reasoning Score</h2>
    <p>The strongest arguments, regardless of upvotes</p>
  </div>

  <table>
    <thead><tr><th>Rank</th><th>Ticker</th><th>AI Score</th><th>Upvotes</th><th>Comment</th></tr></thead>
    <tbody>{top_ai_rows}</tbody>
  </table>

  <div class="section-header">
    <h2>All Scored Recommendations</h2>
    <p>Top 100 by AI score — dimensions: Thesis / Risk / Data / Specificity / Independent</p>
  </div>

  <table>
    <thead><tr><th>Rank</th><th>Ticker</th><th>AI</th><th>T/R/D/S/I</th><th>Upvotes</th><th>Comment</th></tr></thead>
    <tbody>{all_rows}</tbody>
  </table>

  <div class="footer">
    <p>AI reasoning scores — r/ValueInvesting February 2025</p>
  </div>

</div>

<script>
  const ctx = document.getElementById('distChart').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'],
      datasets: [{{
        label: 'Recommendations',
        data: {json.dumps(buckets)},
        backgroundColor: [
          'rgba(255, 74, 94, 0.6)', 'rgba(255, 74, 94, 0.5)',
          'rgba(255, 74, 94, 0.4)', 'rgba(255, 74, 94, 0.3)',
          'rgba(255, 212, 74, 0.4)', 'rgba(255, 212, 74, 0.5)',
          'rgba(74, 255, 145, 0.3)', 'rgba(74, 255, 145, 0.4)',
          'rgba(74, 255, 145, 0.5)', 'rgba(74, 255, 145, 0.6)'
        ],
        borderColor: [
          'rgb(255, 74, 94)', 'rgb(255, 74, 94)',
          'rgb(255, 74, 94)', 'rgb(255, 74, 94)',
          'rgb(255, 212, 74)', 'rgb(255, 212, 74)',
          'rgb(74, 255, 145)', 'rgb(74, 255, 145)',
          'rgb(74, 255, 145)', 'rgb(74, 255, 145)'
        ],
        borderWidth: 1,
        borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
      }},
      scales: {{
        x: {{
          grid: {{ color: 'rgba(30,30,53,0.5)' }},
          ticks: {{ color: '#8888a8', font: {{ family: 'JetBrains Mono' }} }}
        }},
        y: {{
          grid: {{ color: 'rgba(30,30,53,0.5)' }},
          ticks: {{ color: '#8888a8', font: {{ family: 'JetBrains Mono' }} }}
        }}
      }}
    }}
  }});
</script>
</body>
</html>'''

    output_path = os.path.join(RESULTS_DIR, "scoring_preview.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated scoring dashboard: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("prepare", "build"):
        print("Usage:")
        print("  python 3_score_reasoning.py prepare   # Create blind scoring batches")
        print("  python 3_score_reasoning.py build     # Merge scores + build dashboard")
        sys.exit(1)

    if sys.argv[1] == "prepare":
        phase_prepare()
    elif sys.argv[1] == "build":
        phase_build()
