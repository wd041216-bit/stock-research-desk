# CLI Workflow

`stock-research-desk` is intentionally terminal-first.

## One Run

```bash
./bin/research-stock 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事"
```

## Theme Screening

```bash
./bin/research-stock screen "中国机器人" --market CN --count 3
```

This performs:

1. initial screen from public-web evidence
2. candidate-level mini-dossiers with vertical and horizontal web diligence
3. a multi-stage second-screen guru council
4. full deep-research memos for the finalists

Search orchestration policy:

- the model plans search, follow-up search, and critical verification queries
- `web_search` / `web_fetch` are always tried first
- if a tool explicitly errors, the desk falls back to `cross-validated-search` for that step only
- long waits are treated as patience, not as a reason to interrupt the research flow

The second-screen council is no longer a single pass. It now includes:

1. a support round that argues the strongest why-now cases
2. a red-team round that attacks theme fit, evidence quality, and valuation shortcuts
3. a reconsideration round that decides which names still deserve expensive deep research

Artifacts:

- `~/Desktop/Stock Research Desk/screenings/*.md`
- `~/Desktop/Stock Research Desk/screenings/*.json`
- finalist Markdown memos in `~/Desktop/Stock Research Desk/reports/`

## Watchlist

```bash
./bin/research-stock watchlist add 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事" --interval 7d
./bin/research-stock watchlist list
./bin/research-stock watchlist run-due
```

Each watchlist item stores:

- stock name / ticker / market
- research angle
- cadence
- next run time
- latest generated report path

When due entries are processed, the desk also writes:

- `~/Desktop/Stock Research Desk/digests/*-watchlist-digest.md`

## Email Control

QQ Mail works with standard IMAP + SMTP authorization codes.

Example:

```bash
./bin/research-stock email run-once
```

Supported subject formats:

- `research: 赛腾股份 | 603283.SH | CN | 中国故事`
- `screen: 中国机器人 | 3 | CN | 中国故事`
- `watchlist add: 赛腾股份 | 603283.SH | 7d | CN | 中国故事`
- `watchlist list`
- `watchlist run-due`

The desk will:

1. poll unread messages
2. parse supported commands
3. execute the workflow locally
4. reply with a summary and attach the generated memo, screening summary, or digest

Reply formats:

- `Single-Name Desk Note`
- `Screening Brief`
- `Morning Watchlist Brief`
- `Weekly Watchlist Wrap`

## What Happens

1. The CLI loads prior memory from `memory_palace/` if it exists.
2. The market desk searches for industry, cycle, and valuation context.
3. The company desk searches for business, customer, and financial signals.
4. The sentiment desk searches for narrative flow and participant psychology.
5. The comparison desk searches for peers and valuation anchors.
6. The red team attacks weak links.
7. The guru council compresses consensus and disagreement.
8. The MiroFish-style scenario engine writes bull / base / bear paths.
9. The price committee proposes short-, medium-, and long-term targets.
10. The final memo is synthesized into Markdown and JSON.

## Artifacts

- `~/Desktop/Stock Research Desk/reports/*.md`
- `~/Desktop/Stock Research Desk/reports/*.json`
- `~/Desktop/Stock Research Desk/memory_palace/*.json`
- `~/Desktop/Stock Research Desk/screenings/*.md`
- `~/Desktop/Stock Research Desk/screenings/*.json`

## Codex Skill Add-On

The repo also ships a separate Codex skill mode documented in [Codex Skill Mode](codex-skill.md).

That additive mode can:

- let Codex act as the main brain
- use Codex web research first
- produce separate Chinese and English DOCX reports
- move recurring watchlists into Codex automations

The default CLI documented on this page stays Markdown-and-JSON first.

## Recommended Flags

For higher quality:

```bash
research-stock 台积电 --ticker TSM --market US --angle "AI capex" --think high --max-results 5 --max-fetches 6
```

For faster exploratory passes:

```bash
research-stock 宁德时代 --ticker 300750.SZ --market CN --angle "电池出海" --think low --max-results 2 --max-fetches 2
```
