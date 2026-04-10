# CLI Workflow

`stock-research-desk` is intentionally terminal-first.

## One Run

```bash
research-stock 赛腾股份 --ticker 603283.SH --market CN --angle "中国故事"
```

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

- `reports/*.md`
- `reports/*.json`
- `memory_palace/*.json`

## Recommended Flags

For higher quality:

```bash
research-stock 台积电 --ticker TSM --market US --angle "AI capex" --think high --max-results 5 --max-fetches 6
```

For faster exploratory passes:

```bash
research-stock 宁德时代 --ticker 300750.SZ --market CN --angle "电池出海" --think low --max-results 2 --max-fetches 2
```
