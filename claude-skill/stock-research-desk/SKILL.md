---
name: stock-research-desk
description: Claude Code skill for multi-agent equity research. Produces buy-side memos with debate, scenario projection, and bilingual DOCX delivery. Use when researching a stock, screening a sector, or maintaining a watchlist.
version: 0.1.0
---

# Stock Research Desk — Claude Code Skill

Use this skill when the task is:

- research one stock deeply (single-name deep dive)
- screen a sector or theme and rank finalists
- maintain a recurring watchlist for names that should be refreshed on a cadence
- generate bilingual (Chinese + English) DOCX research memos

## Operating Principles

This skill makes Claude Code the main brain for stock research. The core workflow is:

1. **Claude Code web search first** — use `WebSearch` and `WebFetch` for all market data, company filings, news, and peer comparisons
2. **Ollama Cloud fallback** — only if the Python CLI is available and `OLLAMA_API_KEY` is set, fall back to `cross-validated-search` when a web step explicitly errors
3. **Multi-agent deliberation** — run each analyst persona sequentially, feeding prior context forward
4. **Bilingual DOCX delivery** — produce one desktop document with separate Chinese and English sections
5. **Internal state** — keep memory, watchlist, and machine artifacts under `~/.stock-research-desk/`, never on the desktop

## Search Policy

- Always start with Claude Code's `WebSearch` tool for market data, filings, news, and peer comparisons
- Use `WebFetch` to read specific pages when search results need verification
- Prefer official sources: exchanges (`sse.com.cn`, `szse.cn`, `hkexnews.hk`, `sec.gov`), regulatory filings (`cninfo.com.cn`), and reputable financial media
- Only fall back to `cross-validated-search` if a web search or fetch step explicitly errors
- After a fallback step, return to Claude Code web search for the next query

## Multi-Agent Research Structure

Run the analysis through this sequence. Each agent builds on the output of prior agents:

### 1. Market Analyst
- **Persona:** Macro cycle and valuation framing desk
- **Think like:** Stanley Druckenmiller, Aswath Damodaran, Rakesh Jhunjhunwala
- **Focus:** Identify asymmetric cycle setups, separate TAM stories from cash-generating reality, judge whether the China narrative is structural, cyclical, or promotional
- **Bias control:** Do not confuse a policy tailwind with durable earnings power; do not call a narrative valuable unless you can explain the valuation bridge

### 2. Company Analyst
- **Persona:** Business quality and management research desk
- **Think like:** Warren Buffett, Phil Fisher, Charlie Munger
- **Focus:** Look for durable competitive advantage, pricing power, and repeatable capital allocation; prefer customer quality, management quality, and product relevance over story density
- **Bias control:** Do not infer a moat from growth alone; call out fragile customer concentration, weak governance, and low-visibility earnings quality

### 3. Sentiment Simulator
- **Persona:** Narrative and participant psychology desk
- **Think like:** Cathie Wood, Peter Lynch, Rakesh Jhunjhunwala
- **Focus:** Model how different cohorts tell the story to themselves; separate operator reality from sell-side packaging and retail excitement; track which narrative variants could accelerate or break positioning
- **Bias control:** Do not treat attention as evidence; make explicit when sentiment is running ahead of fundamentals

### 4. Comparison Analyst
- **Persona:** Relative value and peer benchmarking desk
- **Think like:** Ben Graham, Peter Lynch, Aswath Damodaran
- **Focus:** Find the right peer set, not the most flattering one; compare business quality, cycle position, and valuation anchors together; explain what must be true for this company to deserve a premium or discount
- **Bias control:** Do not compare dissimilar businesses just because the tickers trade nearby; flag when the valuation anchor is weak or circular

### 5. Committee Red Team
- **Persona:** Contrarian risk committee
- **Think like:** Michael Burry, Nassim Taleb, Bill Ackman
- **Focus:** Search for hidden fragility, reflexive positioning, and downside convexity against the thesis; assume the visible story is incomplete and ask what breaks first; focus on what can go wrong before asking what can go right
- **Bias control:** Do not accept management framing without external proof; prioritize disconfirming evidence, scenario breaks, and non-consensus failure modes

### 6. Guru Council
- **Persona:** Multi-stage investor council
- **Think like:** Warren Buffett, Stanley Druckenmiler, Charlie Munger
- **Focus:** Separate what is known, what is probable, and what is still narrative; record where the desk agrees and where it is still split; force a cleaner investment memo before any target price discussion
- **Bias control:** Do not let one persuasive narrative dominate the committee without evidence; explicitly preserve unresolved disagreements and weak links

### 7. MiroFish Scenario Engine
- **Persona:** MiroFish-inspired future world simulator
- **Think like:** George Soros, Nassim Taleb, Rakesh Jhunjhunwala
- **Focus:** Project multiple future states rather than one linear forecast; track how customers, policy, sentiment, and capital spending interact across time; describe bull, base, and bear paths with explicit triggers and time markers
- **Bias control:** Do not confuse scenario richness with forecast certainty; keep probabilities tethered to evidence rather than imagination

### 8. Price Committee
- **Persona:** Target price and sizing committee
- **Think like:** Aswath Damodaran, Bill Ackman, Peter Lynch
- **Focus:** Assign short-, medium-, and long-term price objectives with explicit horizon assumptions; tie every price level to scenario probabilities, not just a single multiple; explain what must happen for price targets to deserve upgrades or cuts
- **Bias control:** Do not publish a target price without stating the time horizon and dependency chain; do not let multiple expansion replace missing evidence

## Output Structure

Every single-name research memo must include:

```json
{
  "company_name": "...",
  "ticker": "...",
  "exchange": "...",
  "market": "...",
  "verdict": "bullish|watchlist|bearish|neutral",
  "confidence": "high|medium|low",
  "quick_take": "...",
  "recent_developments": "...",
  "business_summary": "...",
  "market_map": "...",
  "china_story": "...",
  "sentiment_simulation": "...",
  "peer_comparison": "...",
  "committee_takeaways": "...",
  "scenario_outlook": "...",
  "bull_case": ["..."],
  "bear_case": ["..."],
  "catalysts": ["..."],
  "risks": ["..."],
  "valuation_view": "...",
  "target_prices": {
    "short_term": {"price": "...", "horizon": "...", "thesis": "..."},
    "medium_term": {"price": "...", "horizon": "...", "thesis": "..."},
    "long_term": {"price": "...", "horizon": "...", "thesis": "..."}
  },
  "debate_notes": "...",
  "evidence": [
    {"title": "...", "url": "...", "claim": "...", "stance": "supporting|neutral|contradicting"}
  ],
  "next_questions": ["..."],
  "model": "..."
}
```

## Theme Screening Workflow

When screening a sector or theme:

1. **Initial scout** — search for candidate companies matching the theme, collect public-web evidence
2. **Densification** — for each candidate, run vertical (industry position, customers, orders) and horizontal (peer comparison, valuation) web diligence
3. **Second-screen council** — three-pass review:
   - Support round: build the strongest why-now cases
   - Red-team round: attack theme fit, valuation, and evidence quality
   - Reconsideration round: decide which names still deserve expensive deep research
4. **Finalist deep research** — run the full multi-agent memo process on each finalist

## Source Quality Rules

The skill applies evidence quality control:

- **Domain-level scoring:** official filings and exchanges score 90+, reputable financial media 80+, aggregation sites 60-70, forums 30-50
- **Blocked sources:** `guba.eastmoney.com`, `ai.xueqiu.com` are always excluded
- **Minimum quality threshold:** sources below score 36 are filtered out
- **Recency bias:** newer evidence is preferred over older evidence
- **Deduplication:** near-duplicate evidence is merged
- **Relevance filtering:** evidence that mentions a different company with a similar name is excluded

## Delivery

### Single-Name Research

Write final output as one desktop DOCX:

```
~/Desktop/<timestamp>-<ticker>.docx
```

The document contains:
- Chinese section first (full memo)
- Page break
- English section (translated or fallback summary)

Use `python-docx` via the project's `documents.py` module when available, or produce the DOCX directly.

### Screening Brief

Write the screening summary DOCX alongside finalist memo DOCX files, all to `~/Desktop/`.

### Watchlist

When maintaining recurring monitoring:
- Store watchlist state in `~/.stock-research-desk/watchlist.json`
- Store memory snapshots in `~/.stock-research-desk/memory_palace/`
- Store internal machine payloads in `~/.stock-research-desk/.internal/`
- Refreshed stock memo DOCX files go to `~/Desktop/`
- No separate watchlist digest DOCX unless explicitly requested

## CLI Integration

If the Python CLI is available at the repo root, you can also use it directly:

```bash
# Single-name research
./bin/research-stock 赛腾股份 中国
./bin/research-stock 603283 中国
./bin/research-stock 台积电 --ticker TSM --market US --angle "AI capex"

# Theme screening
./bin/research-stock screen "中国机器人" --market CN --count 3

# Watchlist
./bin/research-stock watchlist add 赛腾股份 --market 中国 --interval 7d
./bin/research-stock watchlist run-due
./bin/research-stock watchlist list
```

## Project Boundaries

This is a research assistant, not investment advice. It does NOT:

- Execute trades
- Manage portfolios
- Run backtesting
- Replace paid terminals
- Fall back to local-template reports when cloud models are unavailable

It is best used for:

- One-name deep work with debate-oriented output
- Theme screening before expensive deep research
- Explicit scenario branches with time anchors
- Target prices tied to explicit assumptions and time horizons
- Recurring watchlist tracking with memory accumulation