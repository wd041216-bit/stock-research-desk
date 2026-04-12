---
name: stock-research-desk
description: Codex-native stock research workflow for single-name deep dives, theme screening, and watchlist monitoring. Use when researching a stock or sector, producing one desktop DOCX with separate Chinese and English sections, using Codex web search first, falling back to cross-validated-search only on explicit web errors, and setting up Codex automations for recurring coverage.
---

# Stock Research Desk Skill

Use this skill when the task is:

- research one stock deeply
- screen a sector or theme and rank finalists
- maintain a recurring watchlist for names that should be refreshed on a cadence

This skill makes Codex the main brain. The preferred runtime is:

1. Codex web search / page reading first
2. [`cross-validated-search`](https://github.com/wd041216-bit/cross-validated-search) only if a search/fetch step explicitly errors
3. DOCX delivery to the desktop, with Chinese and English versions kept separate
4. Codex automations for watchlist refreshes instead of the repo's older internal scheduler

## Workflow

### 1. Plan the investigation

- define the stock, ticker, market, and angle
- decide whether this is:
  - single-name deep research
  - theme screening
  - recurring watchlist refresh

### 2. Search policy

- always start with Codex web search/open on official filings, exchanges, IR pages, and higher-trust media
- let the model plan follow-up and critical verification queries
- do not interrupt just because a query is slow
- only use `cross-validated-search` if a search or fetch step explicitly errors
- after a fallback step, go back to Codex web search/open for the next query

### 3. Multi-agent research structure (12-step multi-factor pipeline)

Run the analysis through this sequence:

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

The output should always include:

- quick take, verdict, confidence
- business summary, market map, china story
- macro context, flow signal
- sentiment simulation, peer comparison
- technical view, factor exposure
- catalyst calendar
- committee takeaways, debate notes
- bull case, bear case, catalysts, risks
- valuation view
- multi-future scenario outlook
- short / medium / long target prices with time horizons
- evidence list with source quality scores

### 4. Delivery

Write final human-facing reports as one desktop document:

- `~/Desktop/<timestamp>-<ticker-or-name>.docx`

Keep Chinese and English in separate sections inside that one DOCX. Do not create extra watchlist digest DOCX files unless the user explicitly asks for them.

Keep internal state out of the desktop and under the repo/workflow workspace, for example memory snapshots, machine JSON, watchlist queues, and debug artifacts.

If you need the repo's document writer, use:

- [`src/stock_research_desk/documents.py`](references/repo-map.md)

### 5. Watchlist mode

When the user wants recurring monitoring:

- prefer Codex automations instead of the repo's internal watchlist scheduler
- the automation should research the name, regenerate one desktop DOCX with separate Chinese and English sections, and open an inbox item
- use the same evidence policy and target-price structure as single-name work

Read [references/watchlist-automation.md](references/watchlist-automation.md) when preparing a watchlist automation.

## Repo guidance

The repo still contains a standalone CLI, but Codex-native usage should be treated as the preferred operating mode when this skill is available.

Read [references/repo-map.md](references/repo-map.md) before making structural changes.