# Stock Research Desk — Claude Code Integration

This repository is an agentic equity research workflow. Claude Code can use it directly via the skill branch.

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

## 12-Agent Multi-Factor Pipeline

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
| 10 | guru_council | No | Multi-perspective synthesis |
| 11 | mirofish_scenario_engine | No | Bull/base/bear scenario projection |
| 12 | price_committee | Yes | Target prices with explicit horizons |

## Output Fields

- `quick_take`, `verdict`, `confidence`
- `business_summary`, `market_map`, `china_story`
- `macro_context`, `flow_signal`
- `sentiment_simulation`, `peer_comparison`
- `technical_view`, `factor_exposure`
- `catalyst_calendar`
- `committee_takeaways`, `debate_notes`
- `bull_case`, `bear_case`, `catalysts`, `risks`
- `valuation_view`
- `scenario_outlook` (bull/base/bear with triggers)
- `target_prices` (short/medium/long with horizons and theses)
- `evidence` (with source quality scores)

## Branches

- **`main`** — pure agentic workflow (Python CLI engine)
- **`claude-code-skill`** — Claude Code skill version (SKILL.md + prompts + workflow references)

## Core Source Files

| File | Purpose |
|------|---------|
| `src/stock_research_desk/stock_cli.py` | Main CLI, agents, screening, email, watchlist (12-agent pipeline) |
| `src/stock_research_desk/documents.py` | DOCX generation (bilingual, with multi-factor sections) |
| `src/stock_research_desk/persona_pack.py` | 12 investor persona blends |
| `src/stock_research_desk/runtime.py` | JSON parsing and repair |

## Key Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_API_KEY` | required | Ollama Cloud API key (CLI mode) |
| `STOCK_RESEARCH_DESK_HOME` | `~/.stock-research-desk` | Internal state directory |
| `STOCK_RESEARCH_DESK_MODEL` | `glm-5.1:cloud` | Default model (CLI mode) |
| `STOCK_RESEARCH_DESK_OUTPUT_DIR` | `reports` | Desktop delivery directory |

## Testing

```bash
source .venv/bin/activate
pytest -q
```