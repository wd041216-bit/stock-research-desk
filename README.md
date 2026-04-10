# Stock Research Desk

![Stock Research Desk banner](assets/banner.svg)

Cloud-only multi-agent stock research for serious single-name work.

`stock-research-desk` can now do three kinds of work:

- deep research for one stock
- theme / sector screening with initial filter, second filter, and finalist deep dives
- recurring watchlist analysis on a fixed cadence

Everything still stays terminal-first and cloud-only through Ollama Cloud.

## What It Is

This is a terminal-first research desk for one-name equity work.

It is built for the moment after an idea becomes interesting but before you trust yourself to size it. Instead of giving you one smooth paragraph, it runs a staged process:

- evidence-ranked market and company research
- investor-style analyst personas
- red-team challenge and disagreement capture
- MiroFish-style future branches
- explicit short-, medium-, and long-term target prices
- watchlist memory and recurring refresh cycles

![Memo preview](assets/memo-preview.svg)

## Why It Feels Different

Most AI stock tools stop at one of these layers:

- search aggregation
- memo generation
- sentiment scraping

This repo stacks them into one debate-oriented workflow:

- source ranking before synthesis
- multi-agent passes instead of one-shot summary
- committee debate before conclusion
- scenario projection before target prices
- sector screening before expensive deep work
- memory snapshots so repeat runs accumulate context instead of restarting cold

If you want a quick feel for the output, open:

- [Sample Research Memo](docs/sample-memo.md)
- [CLI Workflow](docs/cli-workflow.md)
- [Source Quality Model](docs/source-quality.md)

## Why This Exists

Most AI stock tools fail in one of two ways:

- they are shallow wrappers around web search
- they produce confident prose without enough internal debate

This repo is designed to be stricter:

- cloud-only research path
- evidence ranking and low-quality source filtering
- multi-agent research instead of one-shot summarization
- red team + guru council + future-scenario layer
- target prices always tied to explicit time horizons

It is intentionally narrow:

- no trading execution
- no portfolio management
- no backtesting engine
- no OpenClaw dependency
- no local-model fallback

## 60-Second Start

```bash
git clone https://github.com/wd041216-bit/stock-research-desk.git
cd stock-research-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

Set your cloud key:

```bash
export OLLAMA_API_KEY="your_ollama_cloud_api_key"
```

Run a first memo:

```bash
research-stock 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事"
```

The command writes:

- `~/Desktop/Stock Research Desk/reports/<timestamp>-<ticker>.md`
- `~/Desktop/Stock Research Desk/reports/<timestamp>-<ticker>.json`
- `~/Desktop/Stock Research Desk/memory_palace/<ticker>.json`

Run a theme screen:

```bash
research-stock screen "中国机器人" --market CN --count 3
```

That will:

- do an initial web-based candidate scout
- run a second-screen committee
- run full deep research on the finalists
- save a screening summary to `~/Desktop/Stock Research Desk/screenings/`

Add a recurring watchlist entry:

```bash
research-stock watchlist add 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事" --interval 7d
research-stock watchlist run-due
```

## Full Workflow

The single-name CLI runs a multi-stage desk:

1. `market_analyst`
   Reads the cycle, market structure, China narrative, and valuation frame.
2. `company_analyst`
   Focuses on business quality, customers, financial signals, catalysts, and risks.
3. `sentiment_simulator`
   Simulates multiple participant views from public narrative flow.
4. `comparison_analyst`
   Builds the peer frame and checks whether the name is worth prioritizing.
5. `committee_red_team`
   Forces the breakpoints, weak links, and disconfirming evidence.
6. `guru_council`
   Records consensus, disagreement, and the real verification agenda.
7. `mirofish_scenario_engine`
   Projects bull / base / bear futures with time markers and triggers.
8. `price_committee`
   Produces short-, medium-, and long-term target prices with time horizons.

Every run updates a local `memory_palace/` snapshot so the next pass can continue from prior bull / bear points, open questions, and recent evidence.

For theme screening, the product now uses three layers:

1. initial screen
   Collects candidate names from public-web evidence.
2. second screen
   A stricter committee picks the few names worth expensive deep work.
3. finalist deep research
   The existing multi-agent memo process runs on each finalist.

## Example Output Shape

Each report includes:

- quick take
- market map
- business summary
- sentiment simulation
- peer comparison
- guru council notes
- MiroFish-style future scenarios
- bull / bear / catalysts / risks
- target prices:
  - short term
  - medium term
  - long term

## Configuration

Start from [`.env.example`](.env.example).

Key variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_API_KEY` | required | Ollama Cloud API key |
| `STOCK_RESEARCH_DESK_HOME` | `~/Desktop/Stock Research Desk` | default desktop workspace |
| `STOCK_RESEARCH_DESK_MODEL` | `kimi-k2.5:cloud` | default research model |
| `STOCK_RESEARCH_DESK_THINK` | `high` | reasoning depth |
| `STOCK_RESEARCH_DESK_MAX_RESULTS` | `5` | max web search results per step |
| `STOCK_RESEARCH_DESK_MAX_FETCHES` | `6` | max page fetches per step |
| `STOCK_RESEARCH_DESK_TIMEOUT_SECONDS` | `45` | per-call timeout |
| `STOCK_RESEARCH_DESK_OLLAMA_HOST` | `https://ollama.com` | cloud host |
| `STOCK_RESEARCH_DESK_OUTPUT_DIR` | `reports` | report directory under the desktop workspace |

## Evidence Quality Rules

The repo now includes explicit source quality control:

- domain-level source scoring
- blocked-source filtering
- preference for official filings, exchanges, and higher-trust media
- deduplication and relevance filtering for near-name collisions
- fallback memo generation from ranked evidence instead of raw noisy traces

This does not magically make public web data clean. It does make the workflow more stable and less gullible than a bare search wrapper.

## Docs

- [Sample Research Memo](docs/sample-memo.md)
- [CLI Workflow](docs/cli-workflow.md)
- [Source Quality Model](docs/source-quality.md)
- [Memo Schema](docs/memo-schema.md)

## Testing

```bash
source .venv/bin/activate
pytest -q
```

## Positioning

This is a research assistant, not investment advice.

It is best used when you want:

- one-name deep work
- a debate-oriented memo
- explicit scenario branches
- target prices with time anchors

It is not built for:

- auto-trading
- portfolio construction
- paper trading
- retail hype scraping as a primary signal

## Inspiration

- investor-style analyst decomposition inspired by [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- multi-future branching inspired by [MiroFish](https://github.com/666ghj/MiroFish)
- runtime resilience influenced by the `openstream` design philosophy
