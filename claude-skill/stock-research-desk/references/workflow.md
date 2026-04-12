# Workflow Reference

This document describes the detailed workflow for each mode in the Stock Research Desk.

## Single-Name Research Workflow (12 Steps)

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

### Step 3: Macro & Policy Strategist

**Search focus:**
- Interest rate cycle position and equity risk premium implications
- Credit cycle: spreads, default trends, lending standards
- Monetary policy stance, fiscal stimulus, regulatory risk
- Cross-asset signals: bond/equity/commodity/currency correlation shifts
- FX dynamics and transmission paths to the target stock

**Output fields:**
- `macro_context` — rate environment, credit cycle position, policy stance, transmission paths
- Updated `quick_take` with macro overlay

**Web search queries (examples):**
- `央行 利率 货币政策 立场 {market}`
- `信用周期 信用利差 贷款标准 {market}`
- `股债相关性 跨资产 信号 {year}`
- `{stock_name} 宏观 传导 利率 汇率`

### Step 4: Company Analyst

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

### Step 5: Catalyst & Event Tracker

**Search focus:**
- Upcoming earnings dates, regulatory decision timelines
- M&A rumors, restructuring, spin-offs, activist situations
- Insider buying/selling, share buyback/dilution plans
- Lock-up expirations, index inclusion/exclusion
- Product launch timelines, clinical trial results (for pharma)
- Sector rotation catalysts

**Output fields:**
- `catalyst_calendar` — array of upcoming events with event, date, impact, direction
- Updated `catalysts` list with near-term events
- Updated `risks` list with event-driven risks

**Web search queries (examples):**
- `{stock_name} 财报 发布 日期 {year}`
- `{stock_name} 内幕 交易 回购 增持`
- `{stock_name} 催化剂 事件 监管 审批`

### Step 6: Sentiment Simulator

**Search focus:**
- Public narrative flow: sell-side reports, media coverage, retail sentiment
- Narrative variants and their momentum
- Positioning signals from public data

**Output fields:**
- `sentiment_simulation` — how different market participants view the stock

### Step 7: Technical & Flow Analyst

**Search focus:**
- Current price, recent volume, RSI/MACD context
- Institutional ownership changes, fund flows
- Options market data: IV, put/call ratio, skew, open interest
- Short interest dynamics
- Relative strength vs. index and sector

**Output fields:**
- `technical_view` — key support/resistance, trend stage, momentum signal
- `flow_signal` — institutional flow, ETF dynamics, short interest summary

**Web search queries (examples):**
- `{stock_name} 股价 成交量 技术分析 支撑 阻力`
- `{stock_name} 机构持仓 变动 北向 资金流入`
- `{stock_name} 期权 隐含波动率 看跌看涨比率`

### Step 8: Comparison Analyst

**Search focus:**
- Peer identification and valuation comparison
- Comparable company analysis
- Relative valuation anchors (P/E, P/S, EV/EBITDA)

**Output fields:**
- `peer_comparison` — where this name sits relative to peers

### Step 9: Quant & Factor Analyst

**Search focus:**
- Factor performance data: value, momentum, quality, size, volatility
- Earnings revision momentum and statistical significance
- Factor rotation signals and current regime classification
- Mean-reversion probability assessment

**Output fields:**
- `factor_exposure` — object with value, momentum, quality, size, volatility ratings
- Factor regime assessment and statistical significance notes

**Web search queries (examples):**
- `{stock_name} 因子 暴露 价值 动量 质量 {year}`
- `A股 因子轮动 风格 切换 统计`
- `{stock_name} 盈利修正 一致预期 变动`

### Step 10: Red Team Challenge

**No new search.** Uses prior evidence to:
- Attack weak links in the bull case
- Find disconfirming evidence
- Identify hidden fragility and downside scenarios
- Challenge management framing

**Output fields:**
- `debate_notes` — red team dissent and weak links
- Updated `risks` list

### Step 11: Guru Council

**No new search.** Synthesizes all prior analysis:
- Records consensus views
- Records unresolved disagreements
- Forces a cleaner investment conclusion
- Sets up the scenario engine with key variables
- Now includes quantitative and timing perspectives (Buffett/Druckenmiller/Simons blend)

**Output fields:**
- `committee_takeaways` — what the council agrees and disagrees on

### Step 12: MiroFish Scenario Engine

**No new search.** Projects future states:
- Bull case with explicit triggers and time markers
- Base case with probabilities
- Bear case with trigger events
- Each path includes short-term (0-3m), medium-term (3-12m), long-term (12-36m)

**Output fields:**
- `scenario_outlook` — bull/base/bear paths
- `bull_case` — list of bull catalysts
- `bear_case` — list of bear risks
- `catalysts` — upcoming catalysts
- `risks` — risk factors

### Step 13: Price Committee

**Search focus:**
- Current stock price and recent trading levels
- Sell-side target prices and consensus estimates
- Key catalysts and risks affecting valuation

**Output fields:**
- `target_prices` with `short_term`, `medium_term`, `long_term`
- Each containing `price`, `horizon`, `thesis`

### Step 14: Synthesis and Delivery

- Combine all agent outputs into the final JSON payload
- Include all new fields: technical_view, factor_exposure, catalyst_calendar, macro_context, flow_signal
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

Run the full single-name research workflow (Steps 1-12) on each finalist.

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
1. Run the full single-name research workflow (Steps 1-12)
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