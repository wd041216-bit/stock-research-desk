---
name: stock-research-desk
description: Codex-native stock research workflow for single-name deep dives, theme screening, and watchlist monitoring. Use when researching a stock or sector, producing separate Chinese and English DOCX reports, using Codex web search first, falling back to cross-validated-search only on explicit web errors, and setting up Codex automations for recurring coverage.
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

### 3. Multi-agent research structure

Run the analysis through this sequence:

1. market analyst
2. company analyst
3. sentiment simulator
4. comparison analyst
5. committee red team
6. guru council
7. MiroFish-style scenario engine
8. price committee

The output should always include:

- quick take
- business summary
- market map
- peer comparison
- bull case
- bear case
- catalysts
- risks
- red-team dissent
- multi-future scenario outlook
- short / medium / long target prices with time horizons

### 4. Delivery

Write final reports to:

- `~/Desktop/Stock Research Desk/reports/`
- `~/Desktop/Stock Research Desk/screenings/`
- `~/Desktop/Stock Research Desk/digests/`

Prefer two separate DOCX files:

- Chinese report
- English report

Do not mix Chinese and English inside the same report.

If you need the repo's document writer, use:

- [`src/stock_research_desk/documents.py`](references/repo-map.md)

### 5. Watchlist mode

When the user wants recurring monitoring:

- prefer Codex automations instead of the repo's internal watchlist scheduler
- the automation should research the name, regenerate separate Chinese and English DOCX reports, and open an inbox item
- use the same evidence policy and target-price structure as single-name work

Read [references/watchlist-automation.md](references/watchlist-automation.md) when preparing a watchlist automation.

## Repo guidance

The repo still contains a standalone CLI, but Codex-native usage should be treated as the preferred operating mode when this skill is available.

Read [references/repo-map.md](references/repo-map.md) before making structural changes.
