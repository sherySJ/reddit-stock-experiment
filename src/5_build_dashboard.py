#!/usr/bin/env python3
"""Build the final combined dashboard for the Reddit Stock Experiment."""

import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

TICKER_MAP = {"GOOG": "GOOGL", "B2G": "BTG", "BF": "BF-B"}


def load_all_data():
    """Load all data files needed for the dashboard."""
    with open(os.path.join(DATA_DIR, "recommendations_scored.json")) as f:
        recs = json.load(f)

    with open(os.path.join(DATA_DIR, "backtest_results.json")) as f:
        backtest = json.load(f)

    return recs, backtest


def build_hero_stats(recs, backtest):
    """Build the hero stats row."""
    unique_tickers = set()
    unique_authors = set()
    for r in recs:
        t = TICKER_MAP.get(r["ticker"], r["ticker"])
        unique_tickers.add(t)
        unique_authors.add(r["author"])

    ai_scores = [r["ai_score"] for r in recs]
    avg_ai = sum(ai_scores) / len(ai_scores)
    high_quality = sum(1 for s in ai_scores if s >= 60)

    # Best portfolio return
    best_name = max(
        [(n, p["metrics"]["total_return_pct"]) for n, p in backtest["portfolios"].items() if n != "S&P 500"],
        key=lambda x: x[1]
    )

    return {
        "total_recs": len(recs),
        "unique_tickers": len(unique_tickers),
        "unique_authors": len(unique_authors),
        "avg_ai_score": round(avg_ai, 1),
        "high_quality": high_quality,
        "best_portfolio": best_name[0],
        "best_return": best_name[1],
        "entry_date": backtest["entry_date"],
        "exit_date": backtest["exit_date"],
    }


def build_scoring_examples(recs):
    """Find contrasting examples for the AI scoring section."""
    # Highest upvotes, lowest AI score
    popular_bad = sorted(recs, key=lambda r: (-r["score"], r["ai_score"]))[0]
    # Lowest upvotes, highest AI score
    buried_good = sorted(recs, key=lambda r: (r["score"], -r["ai_score"]))[0]
    # Highest AI score overall
    best_ai = max(recs, key=lambda r: r["ai_score"])

    return popular_bad, buried_good, best_ai


def build_top_ai_table(recs):
    """Build the top 20 by AI score (deduplicated by ticker)."""
    ticker_best = {}
    for r in recs:
        t = TICKER_MAP.get(r["ticker"], r["ticker"])
        if t not in ticker_best or r["ai_score"] > ticker_best[t]["ai_score"]:
            ticker_best[t] = r

    sorted_tickers = sorted(ticker_best.values(), key=lambda r: r["ai_score"], reverse=True)[:20]
    return sorted_tickers


def build_all_recs_table(recs):
    """Build the full recommendations table sorted by upvotes."""
    return sorted(recs, key=lambda r: r["score"], reverse=True)


def generate_dashboard(recs, backtest):
    """Generate the final HTML dashboard."""
    stats = build_hero_stats(recs, backtest)
    popular_bad, buried_good, best_ai = build_scoring_examples(recs)
    top_ai = build_top_ai_table(recs)
    all_recs = build_all_recs_table(recs)

    portfolios = backtest["portfolios"]
    colors = {
        "The Crowd": "#ff6b6b",
        "The Underdogs": "#ffd93d",
        "AI's Picks": "#a855f7",
        "S&P 500": "#4ade80",
    }

    # ---- Chart data ----
    chart_dates = None
    chart_datasets_js = ""
    for name in ["The Crowd", "The Underdogs", "AI's Picks", "S&P 500"]:
        if name not in portfolios:
            continue
        daily = portfolios[name]["daily_values"]
        dates = sorted(daily.keys())
        if chart_dates is None:
            chart_dates = dates
        values = [daily[d] for d in dates]
        data_str = ",".join(str(v) for v in values)
        chart_datasets_js += f"""{{
            label:'{name}',
            data:[{data_str}],
            borderColor:'{colors[name]}',
            backgroundColor:'transparent',
            borderWidth:2.5,
            pointRadius:0,
            tension:0.1
        }},"""

    labels_js = ",".join(f"'{d}'" for d in (chart_dates or []))

    # ---- Summary cards ----
    summary_html = ""
    for name in ["The Crowd", "The Underdogs", "AI's Picks", "S&P 500"]:
        if name not in portfolios:
            continue
        m = portfolios[name]["metrics"]
        color = colors[name]
        ret = m["total_return_pct"]
        ret_color = "#4ade80" if ret >= 0 else "#ff6b6b"
        alpha = m.get("alpha_pct")
        alpha_str = f"{alpha:+.1f}%" if alpha is not None else "—"
        summary_html += f"""
        <div class="summary-card" style="border-top:3px solid {color}">
            <div class="card-name" style="color:{color}">{name}</div>
            <div class="card-return" style="color:{ret_color}">{ret:+.1f}%</div>
            <div class="card-detail">${m['start_value']:,.0f} → ${m['end_value']:,.0f}</div>
            <div class="card-alpha">Alpha: {alpha_str}</div>
        </div>"""

    # ---- Portfolio breakdown tables ----
    portfolio_html = ""
    for name in ["The Crowd", "The Underdogs", "AI's Picks"]:
        if name not in portfolios:
            continue
        m = portfolios[name]["metrics"]
        stocks = portfolios[name]["stock_returns"]
        color = colors[name]
        sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["return_pct"], reverse=True)

        rows = ""
        for ticker, sr in sorted_stocks:
            ret = sr["return_pct"]
            rc = "#4ade80" if ret >= 0 else "#ff6b6b"
            rows += f"""<tr>
                <td style="font-weight:600">{ticker}</td>
                <td>${sr['entry_price']:.2f}</td>
                <td>${sr['current_price']:.2f}</td>
                <td style="color:{rc};font-weight:700">{ret:+.1f}%</td>
            </tr>"""

        alpha_str = f"{m['alpha_pct']:+.1f}%" if m.get('alpha_pct') is not None else "—"
        portfolio_html += f"""
        <div class="portfolio-card">
            <h3 style="color:{color}">{name}</h3>
            <div class="portfolio-stats">
                <span>Return: <b>{m['total_return_pct']:+.1f}%</b></span>
                <span>Alpha: <b>{alpha_str}</b></span>
                <span>Max DD: <b>{m['max_drawdown_pct']:.1f}%</b></span>
                <span>Sharpe: <b>{m['sharpe_ratio']:.2f}</b></span>
            </div>
            <table class="data-table">
                <thead><tr><th>Ticker</th><th>Entry</th><th>Current</th><th>Return</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    # ---- AI scoring examples ----
    def score_badge(score):
        if score >= 60:
            return f'<span class="badge badge-high">{score}</span>'
        elif score >= 40:
            return f'<span class="badge badge-mid">{score}</span>'
        else:
            return f'<span class="badge badge-low">{score}</span>'

    def example_card(rec, label, border_color):
        body = rec["body"][:300].replace("<", "&lt;").replace(">", "&gt;")
        if len(rec["body"]) > 300:
            body += "..."
        return f"""
        <div class="example-card" style="border-left:4px solid {border_color}">
            <div class="example-label">{label}</div>
            <div class="example-meta">{rec['ticker']} &bull; {rec['score']} upvotes &bull; AI Score: {score_badge(rec['ai_score'])}</div>
            <div class="example-body">"{body}"</div>
            <div class="example-explanation">{rec.get('ai_explanation', '')}</div>
        </div>"""

    examples_html = example_card(popular_bad, "Most Upvoted (418 pts)", "#ff6b6b")
    examples_html += example_card(best_ai, f"Highest AI Score ({best_ai['ai_score']})", "#a855f7")
    examples_html += example_card(buried_good, "Best Buried Gem (1 upvote)", "#ffd93d")

    # ---- Score distribution ----
    score_bins = [0] * 10  # 0-9, 10-19, ..., 90-100
    for r in recs:
        bucket = min(r["ai_score"] // 10, 9)
        score_bins[bucket] += 1
    score_bins_js = ",".join(str(b) for b in score_bins)

    # ---- Top 20 AI table ----
    top_ai_rows = ""
    for i, r in enumerate(top_ai, 1):
        t = TICKER_MAP.get(r["ticker"], r["ticker"])
        expl = r.get("ai_explanation", "")[:120]
        if len(r.get("ai_explanation", "")) > 120:
            expl += "..."
        top_ai_rows += f"""<tr>
            <td>{i}</td>
            <td style="font-weight:600">{t}</td>
            <td>{score_badge(r['ai_score'])}</td>
            <td>{r['score']}</td>
            <td class="explanation-cell">{expl}</td>
        </tr>"""

    # ---- All recs table (first 100 for performance) ----
    all_recs_rows = ""
    for r in all_recs[:100]:
        t = TICKER_MAP.get(r["ticker"], r["ticker"])
        body_snip = r["body"][:80].replace("<", "&lt;").replace(">", "&gt;")
        if len(r["body"]) > 80:
            body_snip += "..."
        all_recs_rows += f"""<tr>
            <td style="font-weight:600">{t}</td>
            <td>{r['score']}</td>
            <td>{score_badge(r['ai_score'])}</td>
            <td class="body-cell">{body_snip}</td>
        </tr>"""

    # Correlation stat
    import statistics
    upvotes = [r["score"] for r in recs]
    ai_scores = [r["ai_score"] for r in recs]
    n = len(recs)
    mean_u = statistics.mean(upvotes)
    mean_a = statistics.mean(ai_scores)
    cov = sum((u - mean_u) * (a - mean_a) for u, a in zip(upvotes, ai_scores)) / n
    std_u = statistics.pstdev(upvotes)
    std_a = statistics.pstdev(ai_scores)
    corr = cov / (std_u * std_a) if std_u > 0 and std_a > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>What If AI Read Every Stock Tip on Reddit?</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

  :root {{
    --bg: #0a0a0f;
    --card: #12121a;
    --card-border: #1e1e2e;
    --text: #e0e0e0;
    --text-muted: #888;
    --purple: #a855f7;
    --purple-dim: #7c3aed;
    --green: #4ade80;
    --red: #ff6b6b;
    --yellow: #ffd93d;
    --blue: #6366f1;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }}

  .container {{ max-width: 1300px; margin: 0 auto; padding: 40px 24px; }}

  /* Hero */
  .hero {{
    text-align: center;
    padding: 60px 0 20px;
  }}
  .hero h1 {{
    font-size: 2.6em;
    font-weight: 800;
    background: linear-gradient(135deg, #a855f7, #6366f1, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 12px;
  }}
  .hero .subtitle {{
    color: var(--text-muted);
    font-size: 1.15em;
    max-width: 700px;
    margin: 0 auto;
  }}

  /* Stats bar */
  .stats-bar {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin: 40px 0;
  }}
  .stat-box {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
  }}
  .stat-box .val {{
    font-size: 1.8em;
    font-weight: 800;
    color: var(--purple);
  }}
  .stat-box .label {{
    font-size: 0.8em;
    color: var(--text-muted);
    margin-top: 4px;
  }}

  /* Sections */
  .section {{
    margin: 60px 0;
  }}
  .section h2 {{
    font-size: 1.8em;
    font-weight: 700;
    color: var(--purple);
    margin-bottom: 8px;
  }}
  .section .section-desc {{
    color: var(--text-muted);
    margin-bottom: 25px;
    font-size: 0.95em;
  }}

  /* Key insight callout */
  .insight {{
    background: linear-gradient(135deg, rgba(168,85,247,0.1), rgba(99,102,241,0.1));
    border: 1px solid rgba(168,85,247,0.3);
    border-radius: 16px;
    padding: 30px;
    text-align: center;
    margin: 30px 0;
  }}
  .insight .insight-stat {{
    font-size: 3em;
    font-weight: 900;
    color: var(--purple);
  }}
  .insight .insight-label {{
    font-size: 1.1em;
    color: var(--text-muted);
    margin-top: 5px;
  }}

  /* Summary cards */
  .summary-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
    margin: 30px 0;
  }}
  .summary-card {{
    background: var(--card);
    border-radius: 12px;
    padding: 22px;
    text-align: center;
  }}
  .card-name {{
    font-size: 0.9em;
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .card-return {{
    font-size: 2.2em;
    font-weight: 800;
  }}
  .card-detail {{
    font-size: 0.8em;
    color: var(--text-muted);
    margin-top: 4px;
  }}
  .card-alpha {{
    font-size: 0.8em;
    color: var(--text-muted);
    margin-top: 2px;
  }}

  /* Chart */
  .chart-container {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 30px;
    margin: 30px 0;
  }}

  /* Portfolio cards */
  .portfolios-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }}
  .portfolio-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 25px;
  }}
  .portfolio-card h3 {{
    font-size: 1.3em;
    font-weight: 700;
    margin-bottom: 12px;
  }}
  .portfolio-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 18px;
    font-size: 0.8em;
    color: var(--text-muted);
  }}
  .portfolio-stats b {{ color: var(--text); }}

  /* Example cards */
  .examples-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
  }}
  .example-card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 22px;
  }}
  .example-label {{
    font-size: 0.8em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: 8px;
  }}
  .example-meta {{
    font-size: 0.85em;
    color: var(--text-muted);
    margin-bottom: 10px;
  }}
  .example-body {{
    font-style: italic;
    color: #ccc;
    font-size: 0.9em;
    margin-bottom: 10px;
    line-height: 1.5;
  }}
  .example-explanation {{
    font-size: 0.8em;
    color: var(--text-muted);
    border-top: 1px solid var(--card-border);
    padding-top: 10px;
  }}

  /* Badges */
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.85em;
    font-weight: 700;
  }}
  .badge-high {{ background: rgba(74,222,128,0.15); color: #4ade80; }}
  .badge-mid {{ background: rgba(255,217,61,0.15); color: #ffd93d; }}
  .badge-low {{ background: rgba(255,107,107,0.15); color: #ff6b6b; }}

  /* Tables */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
  }}
  .data-table th {{
    text-align: left;
    padding: 10px 8px;
    color: var(--text-muted);
    font-weight: 600;
    border-bottom: 1px solid var(--card-border);
    font-size: 0.85em;
  }}
  .data-table td {{
    padding: 8px;
    border-bottom: 1px solid rgba(30,30,46,0.5);
  }}
  .data-table tr:hover {{
    background: rgba(168,85,247,0.03);
  }}
  .explanation-cell, .body-cell {{
    color: var(--text-muted);
    font-size: 0.9em;
    max-width: 400px;
  }}

  .table-wrapper {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 25px;
    overflow-x: auto;
  }}

  /* Histogram */
  .hist-container {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 16px;
    padding: 25px;
    max-width: 600px;
  }}

  /* Footer */
  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8em;
    margin-top: 60px;
    padding: 30px 0;
    border-top: 1px solid var(--card-border);
  }}

  @media (max-width: 900px) {{
    .stats-bar {{ grid-template-columns: repeat(3, 1fr); }}
    .summary-row {{ grid-template-columns: repeat(2, 1fr); }}
    .portfolios-grid {{ grid-template-columns: 1fr; }}
  }}
  @media (max-width: 600px) {{
    .stats-bar {{ grid-template-columns: repeat(2, 1fr); }}
    .hero h1 {{ font-size: 1.8em; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HERO -->
  <div class="hero">
    <h1>What If AI Read Every Stock Tip on Reddit?</h1>
    <p class="subtitle">547 stock recommendations from r/ValueInvesting, scored by AI for reasoning quality, backtested over 12 months. Which filter produces the best returns?</p>
  </div>

  <!-- STATS BAR -->
  <div class="stats-bar">
    <div class="stat-box"><div class="val">541</div><div class="label">Threads Scraped</div></div>
    <div class="stat-box"><div class="val">{stats['total_recs']}</div><div class="label">Recommendations</div></div>
    <div class="stat-box"><div class="val">{stats['unique_tickers']}</div><div class="label">Unique Tickers</div></div>
    <div class="stat-box"><div class="val">{stats['unique_authors']}</div><div class="label">Authors</div></div>
    <div class="stat-box"><div class="val">{stats['avg_ai_score']}</div><div class="label">Avg AI Score</div></div>
  </div>

  <!-- KEY INSIGHT -->
  <div class="insight">
    <div class="insight-stat">0.014</div>
    <div class="insight-label">Correlation between Reddit upvotes and AI reasoning quality<br><em>Upvotes tell you nothing about argument quality</em></div>
  </div>

  <!-- RESULTS -->
  <div class="section">
    <h2>The Results</h2>
    <p class="section-desc">$10,000 equal-weight portfolios, all entered March 3, 2025. Which filter beat the market?</p>
    <div class="summary-row">{summary_html}</div>
  </div>

  <!-- PORTFOLIO BREAKDOWN -->
  <div class="section">
    <h2>Portfolio Breakdown</h2>
    <p class="section-desc">Individual stock returns within each portfolio</p>
    <div class="portfolios-grid">{portfolio_html}</div>
  </div>

  <!-- AI SCORING -->
  <div class="section">
    <h2>The AI Scoring</h2>
    <p class="section-desc">Every recommendation scored blind — no knowledge of outcomes. Five dimensions: thesis clarity, risk awareness, data usage, specificity, independent thinking.</p>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:30px">
      <div class="hist-container">
        <h3 style="font-size:1em;margin-bottom:15px;color:var(--text-muted)">Score Distribution</h3>
        <canvas id="histChart" height="250"></canvas>
      </div>
      <div style="display:flex;flex-direction:column;justify-content:center;gap:15px">
        <div class="insight" style="margin:0;padding:20px">
          <div class="insight-stat" style="font-size:2em">{stats['avg_ai_score']}/100</div>
          <div class="insight-label" style="font-size:0.9em">Average AI Score</div>
        </div>
        <div class="insight" style="margin:0;padding:20px">
          <div class="insight-stat" style="font-size:2em">{stats['high_quality']}</div>
          <div class="insight-label" style="font-size:0.9em">of {stats['total_recs']} scored 60+ (quality reasoning)</div>
        </div>
      </div>
    </div>

    <h3 style="font-size:1.1em;margin-bottom:15px">Example Comparisons</h3>
    <div class="examples-grid">{examples_html}</div>
  </div>

  <!-- TOP 20 BY AI -->
  <div class="section">
    <h2>Top 20 by AI Reasoning Score</h2>
    <p class="section-desc">The recommendations AI rated highest for argument quality — regardless of upvotes</p>
    <div class="table-wrapper">
      <table class="data-table">
        <thead><tr><th>#</th><th>Ticker</th><th>AI Score</th><th>Upvotes</th><th>AI Explanation</th></tr></thead>
        <tbody>{top_ai_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- ALL RECS -->
  <div class="section">
    <h2>All Recommendations (Top 100 by Upvotes)</h2>
    <p class="section-desc">Full dataset sorted by Reddit upvotes</p>
    <div class="table-wrapper">
      <table class="data-table">
        <thead><tr><th>Ticker</th><th>Upvotes</th><th>AI Score</th><th>Comment</th></tr></thead>
        <tbody>{all_recs_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- METHODOLOGY -->
  <div class="section">
    <h2>Methodology</h2>
    <div style="background:var(--card);border:1px solid var(--card-border);border-radius:16px;padding:25px;font-size:0.9em;color:var(--text-muted)">
      <ul style="list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <li><b style="color:var(--text)">Source:</b> r/ValueInvesting, February 2025</li>
        <li><b style="color:var(--text)">Collection:</b> 541 threads, 6,457 comments</li>
        <li><b style="color:var(--text)">Entry date:</b> March 3, 2025</li>
        <li><b style="color:var(--text)">Exit date:</b> {stats['exit_date']}</li>
        <li><b style="color:var(--text)">Portfolio size:</b> $10,000 equal-weight</li>
        <li><b style="color:var(--text)">AI model:</b> Claude (Haiku) — blind scoring</li>
        <li><b style="color:var(--text)">Scoring:</b> 5 dimensions, 1-10 each, composite 10-100</li>
        <li><b style="color:var(--text)">Costs:</b> No transaction costs modeled</li>
      </ul>
    </div>
  </div>

  <div class="footer">
    Reddit Stock Experiment &bull; Data collected Feb 2025 &bull; Backtested {stats['entry_date']} to {stats['exit_date']}<br>
    Built with Claude Code &bull; Not financial advice
  </div>

</div>

<script>
// Performance chart removed

// Histogram
new Chart(document.getElementById('histChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: ['0-9','10-19','20-29','30-39','40-49','50-59','60-69','70-79','80-89','90-100'],
    datasets: [{{
      data: [{score_bins_js}],
      backgroundColor: [
        '#ff6b6b','#ff6b6b','#ff6b6b','#ff6b6b',
        '#ffd93d','#ffd93d',
        '#4ade80','#4ade80','#4ade80','#4ade80'
      ],
      borderRadius: 4
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#555', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
      y: {{ ticks: {{ color: '#555' }}, grid: {{ color: '#1a1a2e' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    output_path = os.path.join(RESULTS_DIR, "dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Dashboard saved to {output_path}")
    return output_path


def main():
    print("Building final dashboard...")
    recs, backtest = load_all_data()
    print(f"  {len(recs)} recommendations loaded")
    print(f"  {len(backtest['portfolios'])} portfolios")
    path = generate_dashboard(recs, backtest)
    print(f"\nDone! Open {path} in a browser.")


if __name__ == "__main__":
    main()
