#!/usr/bin/env python3
"""
Merge all score files, combine with recommendations, build portfolios, and backtest.

Entry date: October 1, 2025 (first trading day after September collection window)
Exit date: today (or most recent trading day)
"""
import json
import os
import glob
import sys
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RECS_FILE = os.path.join(DATA_DIR, "recommendations.json")

def merge_scores():
    """Merge all score files into one list."""
    score_files = sorted(glob.glob(os.path.join(DATA_DIR, "scores_*.json")))
    print(f"Found {len(score_files)} score files")

    all_scores = []
    for f in score_files:
        try:
            with open(f) as fh:
                scores = json.load(fh)
                all_scores.extend(scores)
                print(f"  {os.path.basename(f)}: {len(scores)} scores")
        except Exception as e:
            print(f"  Error reading {f}: {e}")

    print(f"\nTotal scores: {len(all_scores)}")
    return all_scores


def merge_with_recs(scores):
    """Merge scores with recommendations."""
    with open(RECS_FILE) as f:
        recs = json.load(f)

    # Build score lookup
    score_lookup = {s["id"]: s for s in scores}

    scored_recs = []
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
        scored_recs.append(r)

    print(f"Scored: {len(scored_recs) - unscored}, Unscored: {unscored}")

    # Save scored recommendations
    scored_path = os.path.join(DATA_DIR, "recommendations_scored.json")
    with open(scored_path, "w") as f:
        json.dump(scored_recs, f, indent=2)
    print(f"Saved to {scored_path}")

    return scored_recs


def build_portfolios(scored_recs):
    """Build the 4 portfolios: Crowd, Underdogs, AI's Picks, S&P 500."""

    # Aggregate by ticker: sum upvotes across all recs for same ticker
    ticker_data = {}
    for r in scored_recs:
        t = r["ticker"]
        if t not in ticker_data:
            ticker_data[t] = {"ticker": t, "total_upvotes": 0, "recs": [], "max_ai_score": 0, "ai_scores": []}
        ticker_data[t]["total_upvotes"] += r.get("score", 0)
        ticker_data[t]["recs"].append(r)
        if r.get("ai_score", 0) > 0:
            ticker_data[t]["ai_scores"].append(r["ai_score"])
        ticker_data[t]["max_ai_score"] = max(ticker_data[t]["max_ai_score"], r.get("ai_score", 0))

    # Compute average AI score per ticker (for tickers with at least one scored rec)
    for t, data in ticker_data.items():
        if data["ai_scores"]:
            data["avg_ai_score"] = sum(data["ai_scores"]) / len(data["ai_scores"])
        else:
            data["avg_ai_score"] = 0

    all_tickers = list(ticker_data.values())

    # Sort by total upvotes
    by_upvotes = sorted(all_tickers, key=lambda x: x["total_upvotes"], reverse=True)

    # Crowd Favorites: Top 10 by total upvotes
    crowd = [t["ticker"] for t in by_upvotes[:10]]

    # Underdogs: Bottom 10 by total upvotes (min 5 upvotes total, at least 2 mentions)
    eligible_underdogs = [t for t in by_upvotes if t["total_upvotes"] >= 5 and len(t["recs"]) >= 2]
    underdogs = [t["ticker"] for t in sorted(eligible_underdogs, key=lambda x: x["total_upvotes"])[:10]]

    # AI's Picks: Top 10 by max AI reasoning score (min 2 recs to avoid single-comment outliers)
    eligible_ai = [t for t in all_tickers if t["max_ai_score"] > 0 and len(t["recs"]) >= 2]
    by_ai = sorted(eligible_ai, key=lambda x: x["max_ai_score"], reverse=True)
    ai_picks = [t["ticker"] for t in by_ai[:10]]

    print("\n=== PORTFOLIOS ===")
    print(f"\nCrowd Favorites (top 10 by upvotes):")
    for t in crowd:
        d = ticker_data[t]
        print(f"  ${t}: {d['total_upvotes']} upvotes, {len(d['recs'])} recs, max AI: {d['max_ai_score']}")

    print(f"\nUnderdogs (bottom 10, min 5 upvotes, min 2 recs):")
    for t in underdogs:
        d = ticker_data[t]
        print(f"  ${t}: {d['total_upvotes']} upvotes, {len(d['recs'])} recs, max AI: {d['max_ai_score']}")

    print(f"\nAI's Picks (top 10 by max reasoning score, min 2 recs):")
    for t in ai_picks:
        d = ticker_data[t]
        print(f"  ${t}: max AI {d['max_ai_score']}, {d['total_upvotes']} upvotes, {len(d['recs'])} recs")

    return crowd, underdogs, ai_picks


def backtest(crowd, underdogs, ai_picks):
    """Run the backtest using yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        print("\nInstalling yfinance...")
        os.system("pip3 install yfinance")
        import yfinance as yf

    import pandas as pd

    entry_date = "2025-10-01"
    exit_date = datetime.now().strftime("%Y-%m-%d")

    all_tickers = list(set(crowd + underdogs + ai_picks + ["SPY"]))
    print(f"\nFetching prices for {len(all_tickers)} tickers...")
    print(f"Entry: {entry_date}, Exit: {exit_date}")

    # Fetch all prices
    data = yf.download(all_tickers, start=entry_date, end=exit_date, auto_adjust=True)

    if data.empty:
        print("ERROR: No price data returned!")
        return

    close = data["Close"] if "Close" in data.columns or len(all_tickers) > 1 else data[["Close"]]

    # Calculate returns
    results = {}
    for ticker in all_tickers:
        try:
            if ticker in close.columns:
                series = close[ticker].dropna()
                if len(series) >= 2:
                    entry_price = series.iloc[0]
                    exit_price = series.iloc[-1]
                    ret = (exit_price / entry_price - 1) * 100
                    results[ticker] = {
                        "entry_price": round(float(entry_price), 2),
                        "exit_price": round(float(exit_price), 2),
                        "return_pct": round(float(ret), 2),
                    }
        except Exception as e:
            print(f"  Error for {ticker}: {e}")

    # Portfolio returns (equal weight)
    def portfolio_return(tickers, name):
        valid = [t for t in tickers if t in results]
        if not valid:
            return {"name": name, "tickers": tickers, "return_pct": 0, "valid": 0}
        avg_ret = sum(results[t]["return_pct"] for t in valid) / len(valid)
        print(f"\n{name}:")
        for t in valid:
            r = results[t]
            print(f"  ${t}: {r['entry_price']} → {r['exit_price']} ({r['return_pct']:+.1f}%)")
        missing = [t for t in tickers if t not in results]
        if missing:
            print(f"  Missing data for: {missing}")
        print(f"  Portfolio return: {avg_ret:+.1f}%")
        return {"name": name, "tickers": valid, "return_pct": round(avg_ret, 2), "valid": len(valid)}

    spy_ret = results.get("SPY", {}).get("return_pct", 0)

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print(f"Period: {entry_date} to {exit_date}")
    print("=" * 60)

    p_crowd = portfolio_return(crowd, "The Crowd (Top 10 by upvotes)")
    p_underdogs = portfolio_return(underdogs, "The Underdogs (Bottom 10)")
    p_ai = portfolio_return(ai_picks, "AI's Picks (Top 10 by reasoning)")
    p_spy = {"name": "S&P 500 (SPY)", "return_pct": round(spy_ret, 2)}

    print(f"\nS&P 500 (SPY): {spy_ret:+.1f}%")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  The Crowd:    {p_crowd['return_pct']:+.1f}%  (alpha: {p_crowd['return_pct'] - spy_ret:+.1f}%)")
    print(f"  The Underdogs: {p_underdogs['return_pct']:+.1f}%  (alpha: {p_underdogs['return_pct'] - spy_ret:+.1f}%)")
    print(f"  AI's Picks:   {p_ai['return_pct']:+.1f}%  (alpha: {p_ai['return_pct'] - spy_ret:+.1f}%)")
    print(f"  S&P 500:      {spy_ret:+.1f}%")

    # Save results
    output = {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "spy_return": spy_ret,
        "portfolios": {
            "crowd": p_crowd,
            "underdogs": p_underdogs,
            "ai_picks": p_ai,
            "spy": p_spy,
        },
        "individual_returns": results,
    }
    output_path = os.path.join(DATA_DIR, "backtest_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    print("Step 1: Merging scores...")
    scores = merge_scores()

    print("\nStep 2: Merging with recommendations...")
    scored_recs = merge_with_recs(scores)

    print("\nStep 3: Building portfolios...")
    crowd, underdogs, ai_picks = build_portfolios(scored_recs)

    print("\nStep 4: Running backtest...")
    backtest(crowd, underdogs, ai_picks)
