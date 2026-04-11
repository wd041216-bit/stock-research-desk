# Repo Map

Use these files when operating the repo through Codex:

- `src/stock_research_desk/stock_cli.py`
  Main workflow, screening logic, email handling, and legacy scheduler support.
- `src/stock_research_desk/documents.py`
  DOCX export layer for Chinese and English report bundles.
- `src/stock_research_desk/persona_pack.py`
  Investor persona blends for the multi-agent workflow.
- `src/stock_research_desk/runtime.py`
  Structured JSON repair and response parsing.
- `tests/test_stock_cli.py`
  High-signal regression coverage for screening, entity normalization, watchlist flow, and report shaping.

Human-facing desktop output:

- `~/Desktop/<timestamp>-<ticker-or-name>.docx`

Internal workspace roots:

- `~/.stock-research-desk/memory_palace/`
- `~/.stock-research-desk/.internal/`
- `~/.stock-research-desk/watchlist.json`
