# CLI Workflow

`stock-research-desk` is intentionally terminal-first.

## One Run

```bash
research-stock 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事"
```

## Theme Screening

```bash
research-stock screen "中国机器人" --market CN --count 3
```

This performs:

1. initial screen from public-web evidence
2. second-screen committee selection
3. full deep-research memos for the finalists

Artifacts:

- `~/Desktop/Stock Research Desk/screenings/*.md`
- `~/Desktop/Stock Research Desk/screenings/*.json`
- finalist memos in `~/Desktop/Stock Research Desk/reports/`

## Watchlist

```bash
research-stock watchlist add 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事" --interval 7d
research-stock watchlist list
research-stock watchlist run-due
```

Each watchlist item stores:

- stock name / ticker / market
- research angle
- cadence
- next run time
- latest generated report path

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

## Recommended Flags

For higher quality:

```bash
research-stock 台积电 --ticker TSM --market US --angle "AI capex" --think high --max-results 5 --max-fetches 6
```

For faster exploratory passes:

```bash
research-stock 宁德时代 --ticker 300750.SZ --market CN --angle "电池出海" --think low --max-results 2 --max-fetches 2
```
