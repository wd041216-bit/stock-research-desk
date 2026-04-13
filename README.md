# Stock Research Desk

[中文说明](README.zh-CN.md)

![Stock Research Desk banner](assets/banner.svg)

A 12-agent multi-factor equity research desk for single-name deep dives, theme screening, recurring watchlists, and bilingual (Chinese + English) document delivery.

## What Makes This Different

Most AI stock tools stop at search aggregation or memo generation. This repo stacks them into one **debate-oriented workflow**:

- **12 specialized analyst desks** run sequentially, each building on prior context
- **Multi-factor coverage**: macro, policy, catalyst, sentiment, technical flow, quant factors — not just fundamentals
- **Red-team challenge** forces dissent before conclusions are drawn
- **Guru council** (Buffett / Druckenmiller / Simons) synthesizes from three distinct investing philosophies
- **MiroFish scenario engine** projects bull / base / bear futures with explicit triggers and time horizons
- **Target prices** always tied to explicit horizons and theses, never pulled from thin air

## The 12-Agent Pipeline

| Step | Agent | Search? | Focus |
|------|-------|---------|-------|
| 1 | market_analyst | Yes | Macro cycle, industry structure, China narrative |
| 2 | macro_policy_strategist | Yes | Interest rates, credit cycle, policy transmission |
| 3 | company_analyst | Yes | Business quality, management, financials |
| 4 | catalyst_event_tracker | Yes | Earnings dates, insider activity, M&A, regulatory |
| 5 | sentiment_simulator | Yes | Narrative temperature, participant psychology |
| 6 | technical_flow_analyst | Yes | Price action, volume, institutional flow, options |
| 7 | comparison_analyst | Yes | Peer comparison, relative valuation anchors |
| 8 | quant_factor_analyst | Yes | Factor exposure, statistical significance, regime |
| 9 | committee_red_team | No | Contrarian challenge, hidden fragility |
| 10 | guru_council | No | Multi-perspective synthesis (Buffett/Druckenmiller/Simons) |
| 11 | mirofish_scenario_engine | No | Bull/base/bear scenario projection |
| 12 | price_committee | Yes | Target prices with explicit horizons |

## Output Fields

Every report includes all of these fields:

| Field | Type | Description |
|-------|------|-------------|
| quick_take | string | One-paragraph verdict with position sizing |
| verdict | string | bullish / bearish / watchlist / neutral |
| confidence | string | high / medium / low |
| business_summary | string | Business model, moat, key signals |
| market_map | string | Industry structure, demand cycle, competitive landscape |
| china_story | string | China narrative — demand, policy, geopolitical angle |
| macro_context | string | Rate environment, credit cycle, policy stance |
| flow_signal | string | Institutional flow, ETF dynamics, short interest |
| sentiment_simulation | string | Narrative temperature, participant psychology |
| peer_comparison | string | Relative valuation, why this name over peers |
| technical_view | string | Support/resistance, trend stage, momentum signal |
| factor_exposure | table | value / momentum / quality / size / volatility ratings |
| catalyst_calendar | table | upcoming events with date, impact, direction |
| committee_takeaways | string | Guru council consensus and disagreement |
| debate_notes | string | Red-team challenge highlights |
| bull_case | list | 3-5 bull points |
| bear_case | list | 3-5 bear points |
| catalysts | list | 3-5 catalyst events |
| risks | list | 3-5 risk factors |
| valuation_view | string | Valuation anchor and framework |
| scenario_outlook | string | Bull / base / bear paths with triggers |
| target_prices | table | short / medium / long with price, horizon, thesis |
| evidence | table | title, url, claim, stance, quality_score |
| next_questions | list | 3-5 open questions for follow-up |

## Modes

| Need | Mode | Output |
| --- | --- | --- |
| One stock, full debate-oriented memo | terminal CLI or Claude Code skill | single desktop DOCX |
| Theme triage before expensive deep work | terminal CLI or Codex skill | screening DOCX + finalist memos |
| Hands-off recurring refreshes | watchlist + mailbox | refreshed stock memos |
| Claude Code as main brain | `claude-skill/` | same DOCX, Claude Code drives research |
| Codex as main brain | `codex-skill/` | same DOCX, Codex drives research |

## 60-Second Start

```bash
git clone https://github.com/wd041216-bit/stock-research-desk.git
cd stock-research-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# put your Ollama Cloud key in .env
./bin/research-stock 赛腾股份 中国
```

For Claude Code or Codex, see the skill manifests in `claude-skill/` and `codex-skill/`.

## Claude Code Skill

The repo ships a Claude Code skill at `claude-skill/stock-research-desk/SKILL.md` with:

- Full 12-agent prompt templates
- Source quality scoring rules (minimum threshold 36)
- Bilingual DOCX delivery instructions
- Watchlist automation reference

## Codex Skill

The repo also ships a Codex skill at `codex-skill/stock-research-desk/SKILL.md` with:

- Codex as main brain, `cross-validated-search` as fallback
- 12-agent multi-factor pipeline
- Same bilingual DOCX delivery

## Theme Screening

```bash
./bin/research-stock screen "中国机器人" --market CN --count 3
```

Three-layer screening: initial scout → second-screen guru council → finalist deep dives.

## Watchlist

```bash
./bin/research-stock watchlist add 赛腾股份 --market 中国 --interval 7d
./bin/research-stock watchlist run-due
```

## Email Interaction

```bash
export STOCK_RESEARCH_DESK_EMAIL_ADDRESS="your_mailbox@example.com"
export STOCK_RESEARCH_DESK_EMAIL_APP_PASSWORD="your_app_password"
./bin/research-stock email run-once
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_API_KEY` | required | Ollama Cloud API key (CLI mode) |
| `STOCK_RESEARCH_DESK_HOME` | `~/.stock-research-desk` | Internal state directory |
| `STOCK_RESEARCH_DESK_MODEL` | `glm-5.1:cloud` | Default model (CLI mode) |
| `STOCK_RESEARCH_DESK_OUTPUT_DIR` | `reports` | Desktop delivery directory |
| `STOCK_RESEARCH_DESK_EMAIL_PROVIDER` | `qq` | Mailbox preset |

## Source Quality Model

The desk uses domain-level source scoring:

| Domain | Score | Category |
|--------|-------|----------|
| cninfo.com.cn | 96 | Official filing |
| sse.com.cn / szse.cn / hkexnews.hk | 95 | Exchange |
| sec.gov | 94 | Official filing |
| yicai.com / caixin.com | 84 | Quality media |
| eastmoney.com | 74 | Aggregator |
| guba.eastmoney.com | 28 (blocked) | Forum noise |

Sources scoring below 36 are filtered out entirely.

## Testing

```bash
source .venv/bin/activate
pytest -q
```

112 tests covering agent prompt builders, pipeline flow, normalization, DOCX generation, and CLI commands.

## Validation Results

Six-stock validation with strict CEO scoring (threshold: 90/100):

| Stock | Score | Verdict |
|-------|-------|---------|
| Microsoft (MSFT) | 92/100 | PASS |
| Alphabet (GOOGL) | 93/100 | PASS |
| Tesla (TSLA) | 92/100 | PASS (optimized from 89) |
| ClearPoint Neuro (CLPT) | 91/100 | PASS (optimized from 87) |
| 赛腾股份 (603283.SH) | 90/100 | PASS |
| 人工智能ETF (515070) | 93/100 | PASS (optimized from 88) |

## What This Is Not

- No trading execution
- No portfolio management
- No backtesting engine
- No local-template fallback

## Inspiration

- Investor-style analyst decomposition inspired by [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- Multi-future branching inspired by [MiroFish](https://github.com/666ghj/MiroFish)
- Runtime resilience influenced by the `openstream` design philosophy

## License

MIT