# Stock Research Desk — Claude Code Skill

[中文说明](README.zh-CN.md)

![Stock Research Desk banner](assets/banner.svg)

This is the **Claude Code skill branch** of [stock-research-desk](https://github.com/wd041216-bit/stock-research-desk). It contains the full skill manifest, 12-agent prompt templates, source quality rules, and workflow references for running the 12-agent multi-factor equity research pipeline directly inside Claude Code.

For the pure Python CLI agentic workflow, see the [`main` branch](https://github.com/wd041216-bit/stock-research-desk/tree/main).

## What This Branch Adds

On top of the core Python engine in `main`, this branch provides:

- `claude-skill/stock-research-desk/SKILL.md` — full skill manifest with 12-agent prompts, evidence rules, and DOCX output schema
- `claude-skill/stock-research-desk/agents/claude.yaml` — 12-agent persona configuration
- `claude-skill/stock-research-desk/references/workflow.md` — detailed 12-step pipeline reference
- `claude-skill/stock-research-desk/references/prompts.md` — full prompt templates for all 12 agents
- `claude-skill/stock-research-desk/references/repo-map.md` — project file structure
- `claude-skill/stock-research-desk/references/watchlist-automation.md` — watchlist scheduling

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

## Quick Reference

**Single-name research:**
```
Research {stock_name} in {market}
```

**Theme screening:**
```
Screen the {theme} sector in {market}, find {count} finalists
```

**Watchlist:**
```
Add {stock_name} to the watchlist with {interval} refresh cycle
```

## Using as a Claude Code Skill

1. Install the skill manifest into your Claude Code configuration
2. The skill will guide Claude Code through the 12-agent pipeline using web search and page fetch
3. Output is one bilingual DOCX on the desktop with Chinese and English sections

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Pure agentic workflow — Python CLI engine with 12-agent pipeline |
| `claude-code-skill` | This branch — Claude Code skill version with SKILL.md, prompts, and workflow references |

## Core Source Files (shared with main)

| File | Purpose |
|------|---------|
| `src/stock_research_desk/stock_cli.py` | Main CLI, agents, screening, email, watchlist (12-agent pipeline) |
| `src/stock_research_desk/documents.py` | DOCX generation (bilingual, with multi-factor sections) |
| `src/stock_research_desk/persona_pack.py` | 12 investor persona blends |
| `src/stock_research_desk/runtime.py` | JSON parsing and repair |

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

## Testing

```bash
source .venv/bin/activate
pytest -q
```

112 tests covering agent prompt builders, pipeline flow, normalization, DOCX generation, and CLI commands.

## Inspiration

- Investor-style analyst decomposition inspired by [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- Multi-future branching inspired by [MiroFish](https://github.com/666ghj/MiroFish)
- Runtime resilience influenced by the `openstream` design philosophy

## License

MIT