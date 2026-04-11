# Codex Skill Mode

`stock-research-desk` now ships with a Codex-native skill:

- [`../codex-skill/stock-research-desk/SKILL.md`](../codex-skill/stock-research-desk/SKILL.md)

This changes the preferred host model.

## Preferred Operating Model

1. Codex is the main brain.
2. Codex uses its own web search / page reading first.
3. `cross-validated-search` is only used if a search or fetch step explicitly errors.
4. Final deliverables should be one desktop DOCX file with a Chinese section first and an English section on a separate page.
5. Recurring watchlists should be implemented with Codex automations.

## Why Keep The CLI

The standalone CLI still matters because it gives the repo:

- a reproducible local execution path
- a packaging surface for GitHub users who are not in Codex
- a concrete implementation of the investor-council workflow
- a document export layer that Codex can also reuse

Both modes now share the same delivery convention:

- one user-facing desktop DOCX that keeps Chinese and English in separate sections for people
- hidden JSON payloads and memory snapshots for machines and follow-up automation

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
