# Workflow Reference

This document describes the detailed workflow for each mode in the Stock Research Desk.

## Single-Name Research Workflow

### Step 1: Resolve Identity

- Accept stock name, ticker, or A-share code (e.g., `603283` auto-appends `.SH`)
- Resolve company name and market from user input
- Load prior memory context from `~/.stock-research-desk/memory_palace/` if it exists

### Step 2: Market Analyst

**Search focus:**
- Macro cycle, industry structure, policy environment
- Market valuation frame (absolute and relative)
- China narrative assessment (structural vs cyclical vs promotional)

**Output fields:**
- `market_map` — industry structure and cycle position
- `china_story` — strategic narrative assessment
- `quick_take` — initial assessment

**Web search queries (examples):**
- `{stock_name} 行业 市场 结构 2024 2025`
- `{stock_name} 宏观 政策 催化`
- `{sector} 估值 分位 周期`

### Step 3: Company Analyst

**Search focus:**
- Business model, revenue mix, customer quality
- Recent orders, contracts, and customer concentration
- Financial signals: margins, cash flow, capital allocation
- Management quality and governance
- Catalysts and risk events

**Output fields:**
- `business_summary` — what the company does and how it makes money
- `recent_developments` — latest news, orders, regulatory changes
- Evidence items with source quality scores

### Step 4: Sentiment Simulator

**Search focus:**
- Public narrative flow: sell-side reports, media coverage, retail sentiment
- Narrative variants and their momentum
- Positioning signals from public data

**Output fields:**
- `sentiment_simulation` — how different market participants view the stock

### Step 5: Comparison Analyst

**Search focus:**
- Peer identification and valuation comparison
- Comparable company analysis
- Relative valuation anchors (P/E, P/S, EV/EBITDA)

**Output fields:**
- `peer_comparison` — where this name sits relative to peers

### Step 6: Red Team Challenge

**No new search.** Uses prior evidence to:
- Attack weak links in the bull case
- Find disconfirming evidence
- Identify hidden fragility and downside scenarios
- Challenge management framing

**Output fields:**
- `debate_notes` — red team dissent and weak links
- Updated `risks` list

### Step 7: Guru Council

**No new search.** Synthesizes all prior analysis:
- Records consensus views
- Records unresolved disagreements
- Forces a cleaner investment conclusion
- Sets up the scenario engine with key variables

**Output fields:**
- `committee_takeaways` — what the council agrees and disagrees on

### Step 8: MiroFish Scenario Engine

**No new search.** Projects future states:
- Bull case with explicit triggers and time markers
- Base case with probabilities
- Bear case with trigger events

**Output fields:**
- `scenario_outlook` — bull/base/bear paths
- `bull_case` — list of bull catalysts
- `bear_case` — list of bear risks
- `catalysts` — upcoming catalysts
- `risks` — risk factors

### Step 9: Price Committee

**No new search.** Assigns target prices:
- Short-term target with time horizon and thesis
- Medium-term target with time horizon and thesis
- Long-term target with time horizon and thesis
- Each price must state its dependency chain

**Output fields:**
- `target_prices` with `short_term`, `medium_term`, `long_term`
- Each containing `price`, `horizon`, `thesis`

### Step 10: Synthesis and Delivery

- Combine all agent outputs into the final payload
- Generate Chinese section first
- Generate English section (translation or structured fallback)
- Write to `~/Desktop/<timestamp>-<ticker>.docx`
- Save memory snapshot to `~/.stock-research-desk/memory_palace/`
- Save machine JSON to `~/.stock-research-desk/.internal/`

## Screening Workflow

### Phase 1: Initial Scout

Search for candidate companies matching the theme:
- Use web search to find companies in the sector/theme
- Collect basic identity data (name, ticker, market)
- Score candidates by relevance and evidence quality
- Limit to a reasonable number (default: 5-8 candidates)

### Phase 2: Densification

For each candidate:
- **Vertical diligence:** industry position, customer quality, order pipeline
- **Horizontal diligence:** peer comparison, relative valuation
- Run focused web searches per candidate
- Build mini-dossiers with evidence

### Phase 3: Second-Screen Council

Three-pass review:
1. **Support round:** Build the strongest why-now cases for each candidate
2. **Red-team round:** Attack theme fit, evidence quality, and valuation shortcuts
3. **Reconsideration round:** Decide which names still deserve expensive deep research

### Phase 4: Finalist Deep Research

Run the full single-name research workflow (Steps 2-10 above) on each finalist.

## Watchlist Workflow

### Adding a Watchlist Entry

```json
{
  "identifier": "赛腾股份",
  "ticker": "603283.SH",
  "market": "CN",
  "angle": "",
  "interval_hours": 168,
  "next_run": "2025-01-20T00:00:00Z",
  "last_report_path": ""
}
```

### Running Due Entries

For each entry where `next_run <= now`:
1. Run the full single-name research workflow
2. Generate the bilingual DOCX memo
3. Update the entry's `next_run` and `last_report_path`
4. Save the watchlist state

## Source Quality Scoring

Domain quality scores (higher = more trusted):

| Domain | Score |
|--------|-------|
| cninfo.com.cn | 96 |
| sse.com.cn | 95 |
| szse.cn | 95 |
| hkexnews.hk | 95 |
| sec.gov | 94 |
| gov.cn | 92 |
| yicai.com | 84 |
| caixin.com | 84 |
| eastmoney.com | 74 |
| finance.sina.com.cn | 68 |
| xueqiu.com | 70 |

Blocked domains (always excluded):
- `guba.eastmoney.com`
- `ai.xueqiu.com`

Minimum quality score: 36

## Evidence Processing

When collecting evidence from web searches:
1. Score each source by domain quality
2. Filter out blocked domains
3. Deduplicate near-identical evidence
4. Check relevance to the target company (not a similarly-named entity)
5. Prefer more recent evidence over older evidence
6. Extract structured claims from each source
7. Assign stance: supporting, neutral, or contradicting

## Memory Context

The skill accumulates memory across runs:
- Prior bull/bear points are carried forward
- Open questions from previous runs are highlighted
- Recent evidence is weighted more heavily
- Memory is stored in `~/.stock-research-desk/memory_palace/`
- Each run updates the memory snapshot for the next pass