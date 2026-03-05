#!/usr/bin/env python3
"""Backtest Reddit stock recommendations: Crowd vs Underdogs vs AI Picks vs S&P 500."""

import pandas as pd
import yfinance as yf
import json
import os
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

ENTRY_DATE = "2025-03-03"
INITIAL_INVESTMENT = 10000

# Ticker mappings for yfinance compatibility
TICKER_MAP = {
    "GOOG": "GOOGL",
    "B2G": "BTG",
    "BF": "BF-B",
    "GTII": "GTBIF",   # Green Thumb Industries — CSE ticker, use US OTC
    "TRUL": "TCNNF",   # Trulieve Cannabis — CSE ticker, use US OTC
}

# Tickers to skip (delisted, etc.)
SKIP_TICKERS = {"GG"}

# ETFs/index funds to exclude from individual stock portfolios
INDEX_ETFS = {"SPY", "VTI", "VOO", "QQQ", "SGOL", "XEQT", "XLE"}


def load_recommendations():
    """Load scored recommendations and aggregate by ticker."""
    path = os.path.join(DATA_DIR, "recommendations_scored.json")
    with open(path) as f:
        recs = json.load(f)

    # Aggregate by ticker: sum upvotes, max AI score, count
    ticker_data = defaultdict(lambda: {
        "total_upvotes": 0, "max_ai": 0, "count": 0,
        "best_upvote_rec": None, "best_ai_rec": None
    })

    for r in recs:
        t = TICKER_MAP.get(r["ticker"], r["ticker"])
        if t in SKIP_TICKERS:
            continue

        ticker_data[t]["count"] += 1
        ticker_data[t]["total_upvotes"] += r["score"]

        if not ticker_data[t]["best_upvote_rec"] or r["score"] > ticker_data[t]["best_upvote_rec"]["score"]:
            ticker_data[t]["best_upvote_rec"] = r

        if r["ai_score"] > ticker_data[t]["max_ai"]:
            ticker_data[t]["max_ai"] = r["ai_score"]
            ticker_data[t]["best_ai_rec"] = r

    return ticker_data


def build_portfolios(ticker_data):
    """Build the four portfolios."""
    # Filter out ETFs/index funds for stock portfolios
    stocks = {t: d for t, d in ticker_data.items() if t not in INDEX_ETFS}

    # The Crowd: Top 10 unique tickers by total upvotes
    crowd = sorted(stocks.items(), key=lambda x: x[1]["total_upvotes"], reverse=True)[:10]

    # The Underdogs: Bottom 10 unique tickers by total upvotes (excluding Crowd, min 5 upvotes)
    crowd_set = set(t for t, _ in crowd)
    non_crowd = {t: d for t, d in stocks.items()
                 if t not in crowd_set and d["total_upvotes"] >= 5}
    underdogs = sorted(non_crowd.items(), key=lambda x: x[1]["total_upvotes"])[:10]

    # AI's Picks: Top 10 unique tickers by max AI score (excluding ETFs)
    ai_picks = sorted(stocks.items(), key=lambda x: x[1]["max_ai"], reverse=True)[:10]

    portfolios = {
        "The Crowd": {
            "tickers": [t for t, _ in crowd],
            "details": [(t, d["total_upvotes"], d["max_ai"], d["count"]) for t, d in crowd],
        },
        "The Underdogs": {
            "tickers": [t for t, _ in underdogs],
            "details": [(t, d["total_upvotes"], d["max_ai"], d["count"]) for t, d in underdogs],
        },
        "AI's Picks": {
            "tickers": [t for t, _ in ai_picks],
            "details": [(t, d["total_upvotes"], d["max_ai"], d["count"]) for t, d in ai_picks],
        },
        "S&P 500": {
            "tickers": ["SPY"],
            "details": [("SPY", 0, 0, 0)],
        },
    }

    return portfolios


def get_prices(tickers, start_date):
    """Download price data from entry date to today."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Downloading prices for {len(tickers)} tickers ({start_date} to {end_date})...")

    data = yf.download(tickers, start=start_date, end=end_date, auto_adjust=True, progress=False)

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data[["Close"]]
        prices.columns = tickers

    return prices


def calculate_portfolio(prices, tickers, initial_investment):
    """Calculate equal-weight portfolio daily values and per-stock returns."""
    available = [t for t in tickers if t in prices.columns and not pd.isna(prices[t].iloc[0])]
    missing = set(tickers) - set(available)
    if missing:
        print(f"  WARNING: Missing data for {missing}, redistributing")

    if not available:
        return None, None

    per_stock = initial_investment / len(available)
    first_prices = prices[available].iloc[0]
    shares = per_stock / first_prices

    # Daily portfolio value
    daily_values = (prices[available] * shares).sum(axis=1)

    # Per-stock returns
    stock_returns = {}
    last_prices = prices[available].iloc[-1]
    for t in available:
        ret = (last_prices[t] / first_prices[t] - 1) * 100
        stock_returns[t] = {
            "entry_price": round(float(first_prices[t]), 2),
            "current_price": round(float(last_prices[t]), 2),
            "return_pct": round(float(ret), 1),
        }

    return daily_values, stock_returns


def calculate_metrics(values, spy_values=None):
    """Calculate performance metrics for a portfolio."""
    start_val = values.iloc[0]
    end_val = values.iloc[-1]
    total_return = (end_val / start_val - 1) * 100

    days = (values.index[-1] - values.index[0]).days
    years = days / 365.25
    annualized = ((end_val / start_val) ** (1 / years) - 1) * 100

    # Max drawdown
    cummax = values.cummax()
    drawdown = (values - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    # Sharpe ratio (2% risk-free)
    daily_returns = values.pct_change().dropna()
    excess = daily_returns - 0.02 / 252
    sharpe = (excess.mean() / excess.std()) * (252 ** 0.5) if excess.std() > 0 else 0

    # Alpha vs S&P 500
    alpha = None
    if spy_values is not None:
        spy_return = (spy_values.iloc[-1] / spy_values.iloc[0] - 1) * 100
        alpha = total_return - spy_return

    return {
        "start_value": round(float(start_val), 2),
        "end_value": round(float(end_val), 2),
        "total_return_pct": round(float(total_return), 1),
        "annualized_return_pct": round(float(annualized), 1),
        "max_drawdown_pct": round(float(max_drawdown), 1),
        "sharpe_ratio": round(float(sharpe), 2),
        "alpha_pct": round(float(alpha), 1) if alpha is not None else None,
        "years": round(float(years), 2),
    }


def main():
    print("=" * 70)
    print("REDDIT STOCK EXPERIMENT — BACKTEST")
    print("=" * 70)

    # Load data
    ticker_data = load_recommendations()
    print(f"Loaded {len(ticker_data)} unique tickers")

    # Build portfolios
    portfolios = build_portfolios(ticker_data)

    print("\nPortfolio compositions:")
    for name, p in portfolios.items():
        print(f"\n  {name}:")
        for t, upvotes, ai, count in p["details"]:
            print(f"    {t:8s} upvotes={upvotes:4d}  ai_score={ai:3d}  mentions={count}")

    # Collect all tickers
    all_tickers = set()
    for p in portfolios.values():
        all_tickers.update(p["tickers"])
    all_tickers.add("SPY")

    # Apply ticker mappings
    mapped = set()
    for t in all_tickers:
        mapped.add(TICKER_MAP.get(t, t))

    # Download prices
    prices = get_prices(list(mapped), ENTRY_DATE)
    print(f"Price data: {prices.shape[0]} trading days, {prices.shape[1]} tickers")

    # Calculate each portfolio
    print("\nCalculating portfolios...")
    results = {}

    # SPY first (needed for alpha calc)
    spy_values, _ = calculate_portfolio(prices, ["SPY"], INITIAL_INVESTMENT)

    for name, p in portfolios.items():
        tickers = [TICKER_MAP.get(t, t) for t in p["tickers"]]
        values, stock_returns = calculate_portfolio(prices, tickers, INITIAL_INVESTMENT)

        if values is None:
            print(f"  SKIPPED {name} — no valid tickers")
            continue

        metrics = calculate_metrics(values, spy_values if name != "S&P 500" else None)

        results[name] = {
            "tickers": p["tickers"],
            "details": p["details"],
            "metrics": metrics,
            "stock_returns": stock_returns,
            "daily_values": {str(d.date()): round(float(v), 2) for d, v in values.items()},
        }

    # Print summary
    print("\n" + "=" * 70)
    print(f"BACKTEST RESULTS: ${INITIAL_INVESTMENT:,} invested {ENTRY_DATE}")
    print("=" * 70)
    header = f"{'Portfolio':<18} {'Final Value':>12} {'Total Return':>13} {'Alpha':>8} {'Max DD':>8} {'Sharpe':>7}"
    print(header)
    print("-" * len(header))

    for name, r in results.items():
        m = r["metrics"]
        alpha_str = f"{m['alpha_pct']:+.1f}%" if m['alpha_pct'] is not None else "   —"
        print(f"{name:<18} ${m['end_value']:>10,.0f} {m['total_return_pct']:>+11.1f}% {alpha_str:>8} {m['max_drawdown_pct']:>6.1f}% {m['sharpe_ratio']:>6.2f}")

    # Per-stock detail
    for name, r in results.items():
        if name == "S&P 500":
            continue
        print(f"\n  {name} — Individual Returns:")
        sorted_stocks = sorted(r["stock_returns"].items(), key=lambda x: x[1]["return_pct"], reverse=True)
        for ticker, sr in sorted_stocks:
            print(f"    {ticker:8s} ${sr['entry_price']:>8.2f} → ${sr['current_price']:>8.2f}  ({sr['return_pct']:+.1f}%)")

    # Save results
    output = {
        "entry_date": ENTRY_DATE,
        "exit_date": str(prices.index[-1].date()),
        "initial_investment": INITIAL_INVESTMENT,
        "portfolios": {},
    }

    for name, r in results.items():
        output["portfolios"][name] = {
            "tickers": r["tickers"],
            "metrics": r["metrics"],
            "stock_returns": r["stock_returns"],
            "daily_values": r["daily_values"],
        }

    output_path = os.path.join(DATA_DIR, "backtest_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Generate HTML preview
    generate_html(output, results)


def generate_html(output, results):
    """Generate the backtest preview HTML dashboard."""
    entry = output["entry_date"]
    exit_date = output["exit_date"]

    # Build chart data (daily values for each portfolio)
    chart_dates = None
    chart_datasets = []
    colors = {
        "The Crowd": "#ff6b6b",
        "The Underdogs": "#ffd93d",
        "AI's Picks": "#a855f7",
        "S&P 500": "#4ade80",
    }

    for name in ["The Crowd", "The Underdogs", "AI's Picks", "S&P 500"]:
        if name not in results:
            continue
        daily = results[name]["daily_values"]
        dates = sorted(daily.keys())
        if chart_dates is None:
            chart_dates = dates
        values = [daily[d] for d in dates]
        chart_datasets.append({
            "label": name,
            "data": values,
            "color": colors.get(name, "#888"),
        })

    # Build individual stock return tables
    portfolio_tables = ""
    for name in ["The Crowd", "The Underdogs", "AI's Picks"]:
        if name not in results:
            continue
        m = results[name]["metrics"]
        stocks = results[name]["stock_returns"]
        sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["return_pct"], reverse=True)

        rows = ""
        for ticker, sr in sorted_stocks:
            ret = sr["return_pct"]
            color = "#4ade80" if ret >= 0 else "#ff6b6b"
            rows += f"""<tr>
                <td style="font-weight:600">{ticker}</td>
                <td>${sr['entry_price']:.2f}</td>
                <td>${sr['current_price']:.2f}</td>
                <td style="color:{color};font-weight:600">{ret:+.1f}%</td>
            </tr>"""

        alpha_str = f"{m['alpha_pct']:+.1f}%" if m['alpha_pct'] is not None else "—"
        portfolio_tables += f"""
        <div class="portfolio-card">
            <h3 style="color:{colors[name]}">{name}</h3>
            <div class="stats-row">
                <div class="stat"><span class="stat-val">{m['total_return_pct']:+.1f}%</span><span class="stat-label">Total Return</span></div>
                <div class="stat"><span class="stat-val">{alpha_str}</span><span class="stat-label">Alpha vs S&P</span></div>
                <div class="stat"><span class="stat-val">{m['max_drawdown_pct']:.1f}%</span><span class="stat-label">Max Drawdown</span></div>
                <div class="stat"><span class="stat-val">{m['sharpe_ratio']:.2f}</span><span class="stat-label">Sharpe</span></div>
            </div>
            <table class="stock-table">
                <thead><tr><th>Ticker</th><th>Entry</th><th>Current</th><th>Return</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    # Summary bar
    spy_m = results.get("S&P 500", {}).get("metrics", {})
    spy_ret = spy_m.get("total_return_pct", 0)

    summary_cards = ""
    for name in ["The Crowd", "The Underdogs", "AI's Picks", "S&P 500"]:
        if name not in results:
            continue
        m = results[name]["metrics"]
        color = colors[name]
        summary_cards += f"""
        <div class="summary-card" style="border-top:3px solid {color}">
            <div class="summary-name" style="color:{color}">{name}</div>
            <div class="summary-return">{m['total_return_pct']:+.1f}%</div>
            <div class="summary-detail">${m['start_value']:,.0f} → ${m['end_value']:,.0f}</div>
        </div>"""

    # Chart.js datasets
    datasets_js = ""
    for ds in chart_datasets:
        data_str = ",".join(str(round(v, 2)) for v in ds["data"])
        datasets_js += f"""{{
            label: '{ds["label"]}',
            data: [{data_str}],
            borderColor: '{ds["color"]}',
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            pointRadius: 0,
            tension: 0.1
        }},"""

    # Sample dates for labels (every 20th date)
    if chart_dates:
        labels = [f"'{d}'" for d in chart_dates]
        labels_js = ",".join(labels)
    else:
        labels_js = ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reddit Stock Experiment — Backtest Results</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0a0a0f; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
    .hero {{ text-align: center; margin-bottom: 50px; }}
    .hero h1 {{ font-size: 2.2em; background: linear-gradient(135deg, #a855f7, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }}
    .hero .subtitle {{ color: #888; font-size: 1.1em; }}
    .pipeline {{ display: flex; justify-content: center; gap: 0; margin: 30px 0; flex-wrap: wrap; }}
    .step {{ padding: 10px 20px; background: #1a1a2e; border: 1px solid #333; font-size: 0.85em; }}
    .step.done {{ border-color: #a855f7; color: #a855f7; }}
    .step.active {{ border-color: #6366f1; background: #1a1a3e; color: #fff; }}
    .step:first-child {{ border-radius: 8px 0 0 8px; }}
    .step:last-child {{ border-radius: 0 8px 8px 0; }}
    .section {{ margin: 50px 0; }}
    .section h2 {{ font-size: 1.6em; color: #a855f7; margin-bottom: 20px; }}
    .summary-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 30px 0; }}
    .summary-card {{ background: #12121a; border-radius: 12px; padding: 20px; text-align: center; }}
    .summary-name {{ font-size: 0.9em; font-weight: 600; margin-bottom: 8px; }}
    .summary-return {{ font-size: 2em; font-weight: 700; color: #fff; }}
    .summary-detail {{ font-size: 0.8em; color: #666; margin-top: 5px; }}
    .chart-container {{ background: #12121a; border-radius: 12px; padding: 25px; margin: 30px 0; }}
    .portfolios-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin: 20px 0; }}
    .portfolio-card {{ background: #12121a; border-radius: 12px; padding: 25px; }}
    .portfolio-card h3 {{ font-size: 1.3em; margin-bottom: 15px; }}
    .stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }}
    .stat {{ text-align: center; }}
    .stat-val {{ display: block; font-size: 1.1em; font-weight: 700; color: #fff; }}
    .stat-label {{ display: block; font-size: 0.7em; color: #666; margin-top: 3px; }}
    .stock-table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
    .stock-table th {{ text-align: left; padding: 8px; color: #666; border-bottom: 1px solid #222; }}
    .stock-table td {{ padding: 8px; border-bottom: 1px solid #1a1a2e; }}
    .note {{ text-align: center; color: #666; font-size: 0.85em; margin-top: 30px; }}
    @media (max-width: 768px) {{
        .summary-row {{ grid-template-columns: repeat(2, 1fr); }}
        .portfolios-grid {{ grid-template-columns: 1fr; }}
        .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="hero">
        <h1>What If AI Read Every Stock Tip on Reddit?</h1>
        <p class="subtitle">Backtest Results: {entry} to {exit_date}</p>
    </div>

    <div class="pipeline">
        <div class="step done">1. Scrape</div>
        <div class="step done">2. Extract</div>
        <div class="step done">3. AI Score</div>
        <div class="step active">4. Backtest</div>
        <div class="step">5. Dashboard</div>
    </div>

    <div class="section">
        <h2>Portfolio Performance</h2>
        <div class="summary-row">{summary_cards}</div>
    </div>

    <div class="section">
        <h2>Portfolio Breakdown</h2>
        <div class="portfolios-grid">{portfolio_tables}</div>
    </div>

    <p class="note">Entry: {entry} &bull; Equal-weight portfolios &bull; No transaction costs</p>
</div>

</body>
</html>"""

    output_path = os.path.join(RESULTS_DIR, "backtest_preview.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Dashboard saved to {output_path}")


if __name__ == "__main__":
    main()
