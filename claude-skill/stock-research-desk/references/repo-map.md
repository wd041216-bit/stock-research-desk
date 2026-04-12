# Repo Map

Use these files when operating the repo through Claude Code:

## Core Source Files

- `src/stock_research_desk/stock_cli.py`
  Main workflow, screening logic, email handling, watchlist management, agent orchestration, prompt construction, source quality scoring, and evidence extraction. This is the largest file and contains the bulk of the business logic.

- `src/stock_research_desk/documents.py`
  DOCX export layer for Chinese and English report bundles. Handles all document formatting, fonts, table layout, and bilingual section assembly.

- `src/stock_research_desk/persona_pack.py`
  Investor persona blends for the multi-agent workflow. Each persona defines role, lead investors, analytical style, primary lenses, and bias controls.

- `src/stock_research_desk/runtime.py`
  Structured JSON repair and response parsing. Handles markdown fences, brace balancing, and JSON extraction from LLM output.

- `src/stock_research_desk/__init__.py`
  Package init, re-exports `main` from `stock_cli`.

## Entry Point

- `bin/research-stock`
  Shell launcher that sets PYTHONPATH and invokes the CLI.

## Test Files

- `tests/test_stock_cli.py`
  High-signal regression coverage for screening, entity normalization, watchlist flow, and report shaping.

## Skill Definitions

- `codex-skill/stock-research-desk/SKILL.md`
  Codex-native skill definition (separate from this Claude Code skill).

- `claude-skill/stock-research-desk/SKILL.md`
  This Claude Code skill definition.

## Key Data Flows

### Single-Name Research

```
User input (stock name/code + market)
  → resolve_stock_name()
  → run_stock_research()
    → market_analyst (web search + analysis)
    → company_analyst (web search + analysis)
    → sentiment_simulator (web search + analysis)
    → comparison_analyst (web search + analysis)
    → committee_red_team (critique)
    → guru_council (synthesize)
    → mirofish_scenario_engine (bull/base/bear)
    → price_committee (target prices)
    → synthesize_buy_side_report()
    → build_report_payload()
    → write_bilingual_report_docx()
    → Desktop delivery
```

### Theme Screening

```
User input (theme + market + count)
  → run_screening_pipeline()
    → run_screening_scout() (initial candidates)
    → run_screening_scout_densification() (vertical/horizontal diligence)
    → run_second_screen_committee() (3-pass review)
    → run_screening_diligence() (finalist deep research)
    → write_bilingual_screening_docx()
    → Desktop delivery
```

### Watchlist

```
watchlist add → save_watchlist()
watchlist run-due → run_due_watchlist()
  → for each due entry, run_stock_research()
  → Desktop delivery of refreshed memos
```

## Human-Facing Desktop Output

- `~/Desktop/<timestamp>-<ticker>.docx` — single-name bilingual memo
- `~/Desktop/<timestamp>-screen-<slug>.docx` — screening summary
- `~/Desktop/<timestamp>-<finalist-ticker>.docx` — finalist deep research memos

## Internal Workspace Roots

- `~/.stock-research-desk/memory_palace/` — memory snapshots for cross-run context
- `~/.stock-research-desk/.internal/` — machine payloads, screening data, debug artifacts
- `~/.stock-research-desk/watchlist.json` — recurring watchlist state