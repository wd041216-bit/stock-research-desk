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

Desktop output roots:

- `~/Desktop/Stock Research Desk/reports/`
- `~/Desktop/Stock Research Desk/screenings/`
- `~/Desktop/Stock Research Desk/digests/`
- `~/Desktop/Stock Research Desk/memory_palace/`
