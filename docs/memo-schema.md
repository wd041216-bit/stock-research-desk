# Memo Schema

Each completed run aims to produce these sections:

- `quick_take`
- `recent_developments`
- `market_map`
- `business_summary`
- `china_story`
- `sentiment_simulation`
- `peer_comparison`
- `committee_takeaways`
- `scenario_outlook`
- `debate_notes`
- `bull_case`
- `bear_case`
- `catalysts`
- `risks`
- `valuation_view`
- `target_prices`
- `evidence`
- `next_questions`

## Recent Developments

`recent_developments` is the memo's freshness layer. It should summarize recent announcements, earnings/order/customer signals, price/news flow, and near-term volatility clues.

Older sources still matter for business quality and long-cycle context, but recent sources should be used to judge marginal change and likely market volatility.

The evidence model may attach:

- `source_date`
- `retrieved_at`
- `quality`

## Target Prices

`target_prices` always uses three buckets:

- `short_term`
- `medium_term`
- `long_term`

Each bucket contains:

- `price`
- `horizon`
- `thesis`

If the price committee fails to produce usable numbers after the cloud model chain has succeeded, the workflow can derive conservative target prices from public price anchors plus the current verdict. If the configured cloud model chain itself is unavailable or times out, the report fails instead of generating a local/template memo.
