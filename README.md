# Can Reddit Beat the Stock Market? An AI-Powered Experiment

An experiment testing whether AI can identify quality stock reasoning in Reddit comments — and whether those picks actually outperform the market.

## What This Is

This project scrapes stock recommendations from r/ValueInvesting, uses Claude to blindly score the quality of each person's reasoning (without knowing which stock they're recommending), then builds portfolios based on those scores and backtests them against the S&P 500.

**The core question:** Does the quality of someone's reasoning predict whether their stock pick will actually perform well?

## How It Works

The experiment runs as a 5-step pipeline, each step building on the last:

```
1_scrape_threads.py    → Scrapes r/ValueInvesting posts from February 2025
2_extract_tickers.py   → Extracts stock ticker recommendations from comments
3_score_reasoning.py   → AI blind-scores reasoning quality (ticker hidden from AI)
4_backtest.py          → Builds portfolios and backtests against S&P 500
5_build_dashboard.py   → Generates interactive HTML dashboard with results
```

### Scoring Dimensions

Each recommendation is scored 1-10 on five dimensions, with the stock ticker stripped so the AI judges reasoning quality alone:

- **Thesis Clarity** — How clear and well-structured is the investment thesis?
- **Risk Awareness** — Does the author acknowledge risks and downsides?
- **Data Usage** — Does the reasoning reference specific numbers, metrics, or data?
- **Specificity** — How specific vs. generic is the analysis?
- **Independent Thinking** — Is this original analysis or just echoing popular sentiment?

### Portfolios

Four portfolios are constructed and compared:

- **Crowd Favorites** — Most-mentioned tickers (popularity)
- **Underdogs** — Least-mentioned tickers with decent reasoning
- **AI Picks** — Top-scored recommendations by reasoning quality
- **S&P 500** — Benchmark

## Setup & Replication

### Prerequisites

- Python 3.10+
- An Anthropic API key (for steps 2, 3 which use Claude)
- Internet connection (for Reddit scraping and stock price data)

### Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Pipeline

Run each script in order from the project root:

```bash
# Step 1: Scrape Reddit threads
python src/1_scrape_threads.py

# Step 2: Extract ticker recommendations
python src/2_extract_tickers.py

# Step 3: Score reasoning quality (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your_key_here
python src/3_score_reasoning.py

# Step 4: Backtest portfolios
python src/4_backtest.py

# Step 5: Build dashboard
python src/5_build_dashboard.py
```

Each step saves its output to the `data/` directory. The final dashboard is saved to `results/dashboard.html`.

### Pre-built Results

If you just want to see the results without running the full pipeline:

- `results/dashboard.html` — Open in any browser to see the interactive dashboard
- `data/recommendations_scored.json` — All 547 scored recommendations
- `data/backtest_results.json` — Portfolio performance data

## September 2025 Validation

The `sept_validation/` directory contains an out-of-sample validation using September 2025 data (post-training cutoff for the AI model). This tests whether the methodology generalizes beyond the original February 2025 dataset.

## Disclaimers

**Built entirely with Claude Code.** This experiment — including all scripts, data processing, analysis, and this README — was built using [Claude Code](https://claude.ai) by Anthropic.

**Reddit content belongs to its authors.** The discussion posts and comments contained in the data files originate from r/ValueInvesting on Reddit. This content was created by the users of that community and belongs to them. It is included here solely for research reproducibility.

**Not financial advice.** This is an experiment, not investment guidance. The portfolios, scores, and results are for educational and research purposes only. Do not make investment decisions based on this analysis.

## License

MIT
