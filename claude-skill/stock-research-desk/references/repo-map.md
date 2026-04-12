# Repo Map

Use these files when operating the repo through Claude Code:

## Core Source Files

- `src/stock_research_desk/stock_cli.py`
  Main workflow (5750+ lines). Contains CLI entry point, agent orchestration, prompt construction, screening pipeline, email handling, watchlist management, evidence processing, source quality scoring, memory context, and report normalization.

- `src/stock_research_desk/documents.py`
  DOCX export layer (709 lines). Handles all document formatting, fonts, table layout, bilingual section assembly, and label localization (Chinese/English).

- `src/stock_research_desk/persona_pack.py`
  Investor persona blends (250+ lines). Each persona defines role_key, title, lead_investors, style_summary, primary_lenses, and bias_controls. Now includes 12 personas: market_analyst, macro_policy_strategist, company_analyst, catalyst_event_tracker, sentiment_simulator, technical_flow_analyst, comparison_analyst, quant_factor_analyst, committee_red_team, guru_council, mirofish_scenario_engine, price_committee.

- `src/stock_research_desk/runtime.py`
  Structured JSON repair and response parsing (54 lines). Handles markdown fences, brace balancing, and JSON extraction from LLM output.

- `src/stock_research_desk/__init__.py`
  Package init, re-exports `main` from `stock_cli`.

## Entry Point

- `bin/research-stock`
  Shell launcher that sets PYTHONPATH and invokes the CLI.

## Test Files

- `tests/test_stock_cli.py`
  High-signal regression coverage for screening, entity normalization, watchlist flow, and report shaping.

## Skill Definitions

- `claude-skill/stock-research-desk/SKILL.md`
  Claude Code skill definition with full prompts, workflow, evidence rules, and output schema. Version 0.3.0 with 12-step multi-factor pipeline.

- `claude-skill/stock-research-desk/agents/claude.yaml`
  Agent configuration with 12 investor personas, execution modes, and source quality scoring.

- `claude-skill/stock-research-desk/references/workflow.md`
  Detailed step-by-step workflow for each research mode (12-step single-name pipeline).

- `claude-skill/stock-research-desk/references/prompts.md`
  Full prompt templates for each agent (12 agents), screening council, and synthesis.

- `claude-skill/stock-research-desk/references/watchlist-automation.md`
  Watchlist scheduling and state management reference.

- `codex-skill/stock-research-desk/SKILL.md`
  Codex-native skill definition (separate from Claude Code skill).

## Key Data Flows

### Single-Name Research (12-Step Pipeline)

```
User input (stock name/code + market)
  → resolve_stock_name()
  → load memory context (~/.stock-research-desk/memory_palace/<ticker>.json)
  → market_analyst (WebSearch + analysis)
  → macro_policy_strategist (WebSearch + analysis)
  → company_analyst (WebSearch + analysis)
  → catalyst_event_tracker (WebSearch + analysis)
  → sentiment_simulator (WebSearch + analysis)
  → technical_flow_analyst (WebSearch + analysis)
  → comparison_analyst (WebSearch + analysis)
  → quant_factor_analyst (WebSearch + analysis)
  → committee_red_team (critique, no new search)
  → guru_council (synthesize, no new search)
  → mirofish_scenario_engine (bull/base/bear, no new search)
  → price_committee (WebSearch + target prices)
  → synthesize_buy_side_report() → JSON payload
  → normalize_report_payload() → cleaned payload
  → translate_structured_payload() → English payload
  → write_bilingual_report_docx() → ~/Desktop/<timestamp>-<ticker>.docx
  → save_memory_context() → ~/.stock-research-desk/memory_palace/<ticker>.json
```

### Theme Screening

```
User input (theme + market + count)
  → run_screening_pipeline()
    → run_screening_scout() (initial candidates via WebSearch)
    → run_screening_scout_densification() (second round if pool is thin)
    → build_screening_doc_payload() (candidate enrichment)
    → run_second_screen_committee() (3-pass: bull → red-team → reconsideration)
    → run_screening_diligence() (finalist deep research, each runs full 12-step pipeline)
    → write_bilingual_screening_docx() → ~/Desktop/<timestamp>-screen-<slug>.docx
    → write_bilingual_report_docx() for each finalist → ~/Desktop/<timestamp>-<ticker>.docx
```

### Watchlist

```
watchlist add → save_watchlist() → ~/.stock-research-desk/watchlist.json
watchlist run-due → run_due_watchlist()
  → for each due entry, run_stock_research()
  → save_memory_context()
  → write_bilingual_report_docx() → ~/Desktop/
  → update next_run timestamp
```

## Human-Facing Desktop Output

- `~/Desktop/<timestamp>-<ticker>.docx` — single-name bilingual memo
- `~/Desktop/<timestamp>-screen-<slug>.docx` — screening summary
- `~/Desktop/<timestamp>-<finalist-ticker>.docx` — finalist deep research memos

## Internal Workspace Roots

- `~/.stock-research-desk/memory_palace/` — memory snapshots for cross-run context
- `~/.stock-research-desk/.internal/` — machine payloads, screening data, debug artifacts
- `~/.stock-research-desk/watchlist.json` — recurring watchlist state