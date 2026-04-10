# Codex Skill Mode

`stock-research-desk` now ships with a Codex-native skill:

- [`../codex-skill/stock-research-desk/SKILL.md`](../codex-skill/stock-research-desk/SKILL.md)

This changes the preferred host model.

## Preferred Operating Model

1. Codex is the main brain.
2. Codex uses its own web search / page reading first.
3. `cross-validated-search` is only used if a search or fetch step explicitly errors.
4. Final deliverables should be separate Chinese and English DOCX files on the desktop.
5. Recurring watchlists should be implemented with Codex automations.

## Why Keep The CLI

The standalone CLI still matters because it gives the repo:

- a reproducible local execution path
- a packaging surface for GitHub users who are not in Codex
- a concrete implementation of the investor-council workflow
- a document export layer that Codex can also reuse

Both modes now share the same delivery convention:

- separate Chinese and English DOCX reports for people
- JSON payloads for machines and follow-up automation

## Recommended Split

- Codex skill:
  - planning
  - web research
  - follow-up search
  - red-team loops
  - automation-driven watchlists
- Repo code:
  - local workflow implementation
  - document generation
  - artifact shaping
  - regression tests
