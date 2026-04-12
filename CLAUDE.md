# Stock Research Desk — Claude Code Integration

This repository includes a Claude Code skill at `claude-skill/stock-research-desk/SKILL.md`.

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

## Skill Location

The Claude Code skill definition is at:
- `claude-skill/stock-research-desk/SKILL.md` — main skill manifest with full prompts, workflow, and output schema
- `claude-skill/stock-research-desk/agents/claude.yaml` — agent configuration
- `claude-skill/stock-research-desk/references/workflow.md` — detailed workflow reference
- `claude-skill/stock-research-desk/references/repo-map.md` — project file structure
- `claude-skill/stock-research-desk/references/watchlist-automation.md` — watchlist scheduling

## Two Skill Modes

This repo ships two skill definitions:

1. **Codex skill** (`codex-skill/`) — uses Codex as main brain, cross-validated-search as fallback
2. **Claude Code skill** (`claude-skill/`) — uses Claude Code as main brain, WebSearch/WebFetch as primary search, Python CLI as optional fallback

Both produce the same bilingual DOCX delivery format.

## Core Source Files

| File | Purpose |
|------|---------|
| `src/stock_research_desk/stock_cli.py` | Main CLI, agents, screening, email, watchlist |
| `src/stock_research_desk/documents.py` | DOCX generation |
| `src/stock_research_desk/persona_pack.py` | Investor persona blends |
| `src/stock_research_desk/runtime.py` | JSON parsing and repair |

## Key Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_API_KEY` | required | Ollama Cloud API key (only needed for CLI mode) |
| `STOCK_RESEARCH_DESK_HOME` | `~/.stock-research-desk` | Internal state directory |
| `STOCK_RESEARCH_DESK_MODEL` | `glm-5.1:cloud` | Default model (CLI mode) |
| `STOCK_RESEARCH_DESK_OUTPUT_DIR` | `reports` | Desktop delivery directory |

## Testing

```bash
source .venv/bin/activate
pytest -q
```