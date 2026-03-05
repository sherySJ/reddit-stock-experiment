#!/usr/bin/env python3
"""
Extract stock tickers from September 2025 comments using pattern matching.
Simpler than AI extraction but much faster and doesn't hit context limits.
Uses same approach as the Feb experiment's AI extraction but with regex + ticker list.
"""
import json
import os
import re
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
COMMENTS_FILE = os.path.join(DATA_DIR, "all_comments.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "recommendations.json")

# Common stock tickers (S&P 500 + frequently mentioned)
# We'll also catch $TICKER patterns and uppercase 2-5 letter words
KNOWN_TICKERS = {
    # Mega caps
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "BRK.A",
    "AVGO", "LLY", "JPM", "V", "UNH", "MA", "XOM", "JNJ", "PG", "HD",
    "COST", "ABBV", "MRK", "CRM", "NFLX", "AMD", "BAC", "TMO", "ADBE", "WMT",
    "CVX", "PEP", "KO", "LIN", "MCD", "CSCO", "ACN", "DHR", "ABT", "TXN",
    "WFC", "PM", "NEE", "INTU", "IBM", "AMGN", "GE", "ISRG", "QCOM", "NOW",
    "CAT", "AMAT", "GS", "RTX", "HON", "BKNG", "LOW", "SYK", "SPGI", "BLK",
    "PFE", "MDLZ", "UBER", "SCHW", "ADP", "VRTX", "ELV", "LRCX", "DE", "PANW",
    "GILD", "BSX", "REGN", "KLAC", "SBUX", "MMC", "C", "AXP", "CI", "ADI",
    "CB", "CME", "MO", "ZTS", "SO", "ICE", "DUK", "SHW", "EQIX", "PGR",
    "CL", "BDX", "ITW", "SLB", "FI", "SNPS", "CDNS", "PYPL", "CMG", "NOC",
    "MCK", "TT", "USB", "MU", "EMR", "AON", "FCX", "PH", "WELL", "MAR",
    "MSI", "ORLY", "GD", "APD", "NSC", "TDG", "HUM", "AJG", "PCAR", "ROP",
    "TGT", "MCO", "AZO", "CARR", "SPG", "ECL", "AIG", "ADSK", "TFC", "CTAS",
    "CPRT", "PSA", "AMP", "MPC", "CCI", "OXY", "GM", "F", "RIVN", "LCID",
    # Popular value / growth names
    "NVO", "TSM", "ASML", "SAP", "BABA", "TCEHY", "PDD", "JD", "SHOP",
    "SQ", "PLTR", "SOFI", "COIN", "RKLB", "SNOW", "DDOG", "NET", "CRWD",
    "ZS", "OKTA", "MELI", "SE", "NU", "GRAB", "DUOL",
    "WBD", "PARA", "DIS", "CMCSA",
    "BMY", "MRNA", "PFE", "BNTX", "VRTX", "BIIB", "ILMN",
    "ELV", "CNC", "HCA", "CVS",
    "INTC", "MU", "ON", "MRVL", "ARM", "SMCI",
    "FSLR", "ENPH", "NEE", "VST", "CEG", "OKLO",
    "BA", "LMT", "RTX", "GD", "NOC",
    "WM", "RSG", "WCN",
    "DVN", "EOG", "FANG", "OXY", "CVX", "XOM", "COP",
    "VZ", "T", "TMUS",
    "LULU", "NKE", "DECK", "ONON",
    "SFM", "KR", "COST",
    "O", "AMT", "EQIX", "SPG",
    "BX", "KKR", "APO",
    "GEV", "GEHC",
    "CSU", "DSGX", "OPEN", "RDDT",
    "CNQ", "SU", "CNI", "CP",
    "VIST", "EGY", "GFR", "IMPP",
    "EQT", "NOV", "GNRC",
    "NBIS", "HIMS", "APP",
    "VEEV", "HOOD",
    "RYCEY", "DNN", "UUUU",
    "BTI", "MO", "PM",
    "AIR", "AIRE",
    "TBN", "VALE", "RIO", "BHP",
    "VFC", "HBI",
    "MMM", "GE",
    "WBA", "CVS",
}

# Company name to ticker mapping
COMPANY_TO_TICKER = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "nvidia": "NVDA", "meta": "META", "facebook": "META",
    "tesla": "TSLA", "berkshire": "BRK.B", "broadcom": "AVGO",
    "eli lilly": "LLY", "lilly": "LLY", "jpmorgan": "JPM", "jp morgan": "JPM",
    "unitedhealth": "UNH", "united health": "UNH", "exxon": "XOM",
    "johnson & johnson": "JNJ", "j&j": "JNJ", "procter": "PG",
    "home depot": "HD", "costco": "COST", "abbvie": "ABBV", "merck": "MRK",
    "salesforce": "CRM", "netflix": "NFLX", "walmart": "WMT",
    "pepsi": "PEP", "pepsico": "PEP", "coca-cola": "KO", "coke": "KO",
    "mcdonald": "MCD", "cisco": "CSCO", "intel": "INTC",
    "palantir": "PLTR", "snowflake": "SNOW", "coinbase": "COIN",
    "shopify": "SHOP", "spotify": "SPOT", "uber": "UBER",
    "disney": "DIS", "boeing": "BA", "lockheed": "LMT",
    "novo nordisk": "NVO", "novo": "NVO", "taiwan semi": "TSM", "tsmc": "TSM",
    "alibaba": "BABA", "constellation software": "CSU", "constellation": "CSU",
    "duolingo": "DUOL", "rocket lab": "RKLB",
    "sprouts": "SFM", "sprouts farmers": "SFM",
    "opendoor": "OPEN", "reddit": "RDDT",
    "lululemon": "LULU", "deckers": "DECK", "on holding": "ONON",
    "centene": "CNC", "elevance": "ELV",
    "hershey": "HSY", "waste management": "WM",
    "vista energy": "VIST", "devon": "DVN", "diamondback": "FANG",
    "first solar": "FSLR", "moderna": "MRNA",
    "oracle": "ORCL", "adobe": "ADBE", "crowdstrike": "CRWD",
    "rolls royce": "RYCEY", "denison": "DNN",
    "nebius": "NBIS", "hims": "HIMS",
    "canadian natural": "CNQ", "cn rail": "CNI",
    "pfizer": "PFE", "bristol": "BMY", "bristol-myers": "BMY",
    "sofi": "SOFI", "block": "SQ", "square": "SQ",
    "paypal": "PYPL", "chipotle": "CMG",
    "maersk": "AMKBY",
}

# Words that look like tickers but aren't
FALSE_POSITIVES = {
    "CEO", "CFO", "CTO", "COO", "IPO", "ETF", "GDP", "EPS", "DCF", "FCF",
    "P/E", "PE", "ROE", "ROI", "ROA", "EBITDA", "CAGR", "YOY", "QOQ",
    "IMO", "TBH", "FWIW", "FYI", "AFAIK", "IIRC", "TIL", "PSA",
    "DD", "TA", "FA", "DCA", "DRIP", "IRA", "FED", "SEC", "NYSE", "MOAT",
    "ATH", "ATL", "AI", "ML", "US", "UK", "EU", "USA", "USD", "CAD",
    "OTC", "ITM", "OTM", "IV", "HFT", "OP", "TLDR", "EDIT", "TL",
    "IMHO", "SMH", "WTF", "LOL", "LMAO", "HODL", "YOLO", "FOMO",
    "FIRE", "NFA", "DYOR", "NDA", "APR", "AMA", "BTW", "PMI",
    "CPI", "PPI", "BLS", "FOMC", "QE", "QT", "AGI", "LLM",
    "SAGD", "CRUD", "NYSE", "API", "SDK", "TSX", "OTC",
    "ITM", "OTM", "IV", "DTE", "SBC", "TTM", "LTM",
    "OBBB", "CAPEX", "OPEX", "M&A",
}

# Bullish signal words
BULLISH_SIGNALS = [
    "buy", "buying", "bought", "adding", "added", "accumulating",
    "bullish", "bull case", "undervalued", "cheap", "great value",
    "good value", "fair value", "great price", "good price", "dirt cheap",
    "long", "going long", "im in", "i'm in", "i am in",
    "holding", "hold", "will hold", "still holding",
    "recommend", "pick", "my pick", "top pick",
    "love", "like", "great company", "amazing company",
    "upside", "potential", "no brainer", "steal",
    "loading", "loaded up", "backed up the truck",
    "position", "my position", "started a position", "entered",
    "conviction", "high conviction", "strong conviction",
]

# Bearish signal words
BEARISH_SIGNALS = [
    "sell", "selling", "sold", "short", "shorting",
    "bearish", "bear case", "overvalued", "expensive", "too expensive",
    "avoid", "stay away", "wouldn't touch", "pass",
    "garbage", "trash", "junk", "scam", "ponzi",
    "dump", "dumping", "crashed", "falling knife",
    "value trap", "bag holder",
]


def extract_tickers_from_text(text):
    """Extract potential stock tickers from comment text."""
    tickers = set()

    # Pattern 1: $TICKER
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text)
    for t in dollar_tickers:
        if t not in FALSE_POSITIVES and len(t) >= 2:
            tickers.add(t)

    # Pattern 2: Known tickers as standalone words (uppercase, 2-5 chars)
    words = re.findall(r'\b([A-Z]{2,5})\b', text)
    for w in words:
        if w in KNOWN_TICKERS and w not in FALSE_POSITIVES:
            tickers.add(w)

    # Pattern 3: Company name mapping (case-insensitive)
    text_lower = text.lower()
    for name, ticker in COMPANY_TO_TICKER.items():
        if name in text_lower:
            tickers.add(ticker)

    return tickers


def is_bullish(text):
    """Check if the comment expresses bullish sentiment."""
    text_lower = text.lower()
    bullish_count = sum(1 for s in BULLISH_SIGNALS if s in text_lower)
    bearish_count = sum(1 for s in BEARISH_SIGNALS if s in text_lower)
    return bullish_count > bearish_count


def main():
    with open(COMMENTS_FILE) as f:
        comments = json.load(f)

    print(f"Processing {len(comments)} comments...")

    recommendations = []
    for comment in comments:
        body = comment.get("body", "")
        if not body or len(body) < 5:
            continue

        tickers = extract_tickers_from_text(body)
        if not tickers:
            continue

        # Check if bullish
        if not is_bullish(body):
            continue

        for ticker in tickers:
            recommendations.append({
                "comment_id": comment["id"],
                "thread_id": comment["thread_id"],
                "thread_title": comment.get("thread_title", ""),
                "ticker": ticker,
                "author": comment.get("author", "[deleted]"),
                "score": comment.get("score", 0),
                "body": body[:1000],
                "sentiment": "bullish",
            })

    # Normalize ticker aliases
    TICKER_ALIASES = {"GOOG": "GOOGL", "BRK.A": "BRK.B", "FB": "META"}
    for r in recommendations:
        r["ticker"] = TICKER_ALIASES.get(r["ticker"], r["ticker"])

    # Deduplicate: same author + same ticker → keep highest score
    seen = {}
    for r in recommendations:
        key = (r["author"], r["ticker"])
        if key not in seen or r["score"] > seen[key]["score"]:
            seen[key] = r
    deduped = sorted(seen.values(), key=lambda x: x["score"], reverse=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(deduped, f, indent=2)

    # Stats
    tickers = {}
    for r in deduped:
        t = r["ticker"]
        if t not in tickers:
            tickers[t] = 0
        tickers[t] += 1

    top = sorted(tickers.items(), key=lambda x: x[1], reverse=True)[:20]

    print(f"\nTotal recommendations (before dedup): {len(recommendations)}")
    print(f"After dedup (unique author+ticker): {len(deduped)}")
    print(f"Unique tickers: {len(tickers)}")
    print(f"\nTop 20 most mentioned:")
    for t, count in top:
        print(f"  ${t}: {count} mentions")


if __name__ == "__main__":
    main()
