# Case Study: SaiTeng (603283.SH)

This page shows how `stock-research-desk` behaves on a realistic single-name workflow.

It is intentionally public-safe:

- no private notes
- no local paths
- no copied report payloads from a live user workspace
- no account-specific settings

The goal is to show what the desk is good at, where it stays conservative, and what kind of final recommendation it produces when evidence is still mixed.

## Research Setup

- Name: `SaiTeng`
- Ticker: `603283.SH`
- Market: `CN`
- Angle: `China narrative`
- Output style: Chinese and English DOCX plus JSON

## Why This Name Was Interesting

SaiTeng sits at the intersection of:

- advanced manufacturing
- automation equipment
- semiconductor localization and industrial upgrade narratives

That makes it a good test case for the desk because it is exactly the sort of company that can look compelling in narrative form while still hiding important questions in customer mix, order quality, and cyclicality.

## What The Desk Did

The single-name workflow runs as a staged debate, not a one-shot summary.

1. `market_analyst`
   Built the market frame around automation, capex timing, and the relevant China story.
2. `company_analyst`
   Focused on business quality, customer quality, financial signals, catalysts, and risks.
3. `sentiment_simulator`
   Modeled how different public-market participants might narrate the stock.
4. `comparison_analyst`
   Built the peer frame and checked whether the name deserved more time than adjacent names.
5. `committee_red_team`
   Forced the workflow to defend itself against weak evidence, narrative leakage, and valuation shortcuts.
6. `guru_council`
   Compressed the disagreement into a clearer decision frame.
7. `mirofish_scenario_engine`
   Generated bull, base, and bear futures with triggers and timing.
8. `price_committee`
   Produced short-, medium-, and long-term target prices tied to explicit horizons.

## What The Desk Liked

- The company fits a structural industrial-upgrade narrative rather than a random one-quarter story.
- There is a plausible path for sentiment and valuation improvement if higher-quality demand keeps becoming visible.
- The workflow found enough evidence to justify continued coverage instead of immediate rejection.

## What Made The Desk Stay Conservative

- Customer concentration remained a real concern.
- Public-web evidence was not yet strong enough to fully separate durable business quality from good storytelling.
- The desk treated the valuation case as conditional on cleaner proof, not as something that was already earned.

## Public-Safe Output Shape

The desk's public-safe verdict for this kind of case looks like:

- `verdict`: `watchlist`
- `confidence`: `medium` or `high`, depending on evidence quality
- `bull case`: structural narrative and upside if mix improves
- `bear case`: concentration, cyclicality, and the risk that narrative outruns fundamentals
- `catalysts`: cleaner disclosure, new customer wins, better order visibility
- `risks`: project-driven revenue, concentration, sentiment cooling before fundamentals confirm

## Why This Is A Useful Example

This example is not impressive because it produces a bullish answer.

It is useful because it shows the desk doing something harder:

- keeping the name alive
- refusing to jump to high conviction
- preserving the disagreement
- turning that disagreement into a practical verification agenda

That is a much better stress test for a research workflow than a cherry-picked obvious winner.

## What This Case Demonstrates About The Repo

- It is not just a search wrapper.
- It separates screening budget from deep-research budget.
- It keeps a red-team layer in the final path.
- It can produce human-ready bilingual documents without giving up machine-readable JSON.
- It is designed to be used repeatedly on the same name through watchlists and recurring refreshes.

## Where To Go Next

- [Sample Research Memo](sample-memo.md)
- [Sample Screening Summary](sample-screening.md)
- [CLI Workflow](cli-workflow.md)
- [Source Quality Model](source-quality.md)
