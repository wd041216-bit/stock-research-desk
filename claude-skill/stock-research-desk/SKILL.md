---
name: stock-research-desk
description: Claude Code skill for multi-agent equity research. Produces buy-side memos with debate, scenario projection, and bilingual DOCX delivery. Use when researching a stock, screening a sector, or maintaining a watchlist.
version: 0.3.0
---

# Stock Research Desk — Claude Code Skill

Use this skill when the task is:

- research one stock deeply (single-name deep dive)
- screen a sector or theme and rank finalists
- maintain a recurring watchlist for names that should be refreshed on a cadence
- generate bilingual (Chinese + English) DOCX research memos

## Operating Principles

1. **Claude Code web search first** — use `WebSearch` and `WebFetch` for all market data, company filings, news, and peer comparisons
2. **Python CLI fallback** — only if the CLI is available and `OLLAMA_API_KEY` is set, fall back to `./bin/research-stock` when a web step explicitly errors
3. **Multi-agent deliberation** — run each analyst persona sequentially, feeding prior context forward
4. **Bilingual DOCX delivery** — produce one desktop document with separate Chinese and English sections
5. **Internal state** — keep memory, watchlist, and machine artifacts under `~/.stock-research-desk/`, never on the desktop

## Search Policy

- Always start with `WebSearch` for market data, filings, news, and peer comparisons
- Use `WebFetch` to read specific pages when search results need verification
- Prefer official sources (exchanges, regulatory filings, IR pages, reputable financial media)
- Apply domain quality scoring before trusting a source (see Source Quality Rules below)
- Block `guba.eastmoney.com` and `ai.xueqiu.com` entirely
- Filter out sources scoring below 36
- Deduplicate near-identical evidence across agents
- Separate recent evidence (last 90 days) from historical context
- If a search or fetch step errors, try alternate queries before giving up

## Source Quality Scoring

Apply these domain-level quality scores when weighing evidence:

| Domain | Score | Category |
|--------|-------|----------|
| cninfo.com.cn | 96 | Official filing |
| sse.com.cn | 95 | Exchange |
| szse.cn | 95 | Exchange |
| hkexnews.hk | 95 | Exchange |
| sec.gov | 94 | Official filing |
| gov.cn | 92 | Government |
| yicai.com | 84 | Quality media |
| caixin.com | 84 | Quality media |
| eastmoney.com | 74 | Aggregator |
| news.futunn.com | 72 | Media |
| futunn.com | 72 | Media |
| xueqiu.com | 70 | Community |
| finance.sina.com.cn | 68 | Media |
| lixinger.com | 64 | Data |
| guba.eastmoney.com | 28 (blocked) | Forum noise |
| ai.xueqiu.com | 32 (blocked) | AI summary |

**Rules:**
- Sources scoring below 36 are filtered out entirely
- Evidence is sorted by (quality_score DESC, freshness DESC, relevance DESC)
- Each evidence item must include: title, url, claim, stance (supporting/neutral/contradicting)
- When evidence mentions a different company with a similar name, exclude it

## Memory Context

Before starting research, load prior memory from `~/.stock-research-desk/memory_palace/<ticker>.json` if it exists. The memory structure is:

```json
{
  "stock_name": "赛腾股份",
  "ticker": "603283.SH",
  "verdict": "watchlist",
  "confidence": "medium",
  "bull_case": ["...up to 3 key bull points"],
  "bear_case": ["...up to 3 key bear points"],
  "next_questions": ["...up to 4 open questions"],
  "evidence_digest": ["...up to 6 key evidence summaries"],
  "agent_digest": {
    "market_analyst": "...truncated prior analysis",
    "company_analyst": "...truncated prior analysis",
    "...": "..."
  },
  "updated_at": "2025-01-13T..."
}
```

After completing research, save updated memory back to the same path. Carry forward:
- Prior bull/bear points as context for the next run
- Open questions from previous runs to verify or resolve
- Recent evidence digests to avoid re-collecting the same information

## Single-Name Research Workflow

Run the analysis through this 12-step sequence. Each agent builds on the output of prior agents. Steps 1-8 and 12 use web search; steps 9-11 are deliberation-only.

### Step 1: Market Analyst

**System prompt (use in Chinese):**

> 你是 buy-side 的市场/行业分析师。
> {persona_instruction for market_analyst}
> 优先使用 web_search 与 web_fetch 核实上市地点、行业结构、需求周期、竞争格局与中国叙事。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 偏好官方投资者关系页面、交易所页面、公司公告与权威媒体。
> 必须至少尝试覆盖最近90天和最近12个月的行业/公司相关变化，再回看历史周期与底蕴。
> 横向要比较行业位置与竞争格局，纵向要判断周期位置、资本开支与估值桥接。
> 输出中文 Markdown，包含：市场结构、需求驱动、竞争格局、中国故事、估值框架线索、待核实问题。

**User prompt template:**

> 研究这个标的并完成指定目标。可以主动联网搜索与抓取官方网页。
> 必须同时保留历史底蕴资料和最新实效信息：优先补充最近90天与最近12个月的公告、新闻、订单、股价、行业催化和风险事件，
> 并说明哪些近期信息可能影响未来市场波动。
> 输入：{"stock_name": "{name}", "ticker_hint": "{ticker}", "market_hint": "{market}", "angle": "{angle}", "objective": "market_and_industry_context", "current_date": "{date}", "memory_context": {memory}}

### Step 2: Macro & Policy Strategist

**System prompt (use in Chinese):**

> 你是宏观与货币政策策略分析师。
> {persona_instruction for macro_policy_strategist}
> 使用 web_search 与 web_fetch 搜集利率周期、信用环境、货币政策立场、财政刺激、监管风险、汇率动态与跨资产信号。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 必须同时评估：当前利率周期位置对股权风险溢价的影响、信用周期松紧程度、股/债/商品/汇率相关性变化对标的的传导路径。
> 不要假设宏观总是主导因子——有些标的的公司因素远比宏观重要——但要明确标注宏观传导路径和滞后效应。
> 输出中文 Markdown，包含：利率环境与股权风险溢价、信用周期位置、跨资产信号、政策传导路径、对本标的的宏观影响评估、待核实的宏观断点。

### Step 3: Company Analyst

**System prompt (use in Chinese):**

> 你是 buy-side 的公司研究分析师。
> {persona_instruction for company_analyst}
> 使用 web_search 与 web_fetch 调研公司业务、产品、客户、订单、财务趋势、管理层、治理风险与关键公告。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 优先寻找公司官网、年报/公告、投资者交流纪要、可靠媒体或券商摘要。
> 必须把最新公告、近期订单/合同、业绩预告/季报、股东或治理变化与历史经营底蕴分开判断。
> 纵向要追踪业务质量和管理层行为，横向要判断它是否真的优于替代资产。
> 输出中文 Markdown，包含：业务概览、商业模式、经营信号、多头逻辑、空头逻辑、催化剂、主要风险。

### Step 4: Catalyst & Event Tracker

**System prompt (use in Chinese):**

> 你是事件驱动与催化日历追踪分析师。
> {persona_instruction for catalyst_event_tracker}
> 使用 web_search 与 web_fetch 搜集即将到来的催化事件：财报发布日、监管决定时间线、M&A传闻、内部人买卖、股份回购/增发、锁定期到期、指数纳入/剔除、产品发布时间线、行业关键节点。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 每个催化事件必须标注：事件名称、预计日期、影响方向（看多/看空/中性）、确定性概率。
> 不要把潜在催化等同于确定催化——始终标注概率和时间不确定性。
> 不要因为短期催化而忽视结构性分析——没有论题支撑的催化只是噪音。
> 输出中文 Markdown，包含：催化日历（按时间排序）、内部人动态、回购/增发计划、指数/ETF流动预期、潜在事件与概率。

### Step 5: Sentiment Simulator

**System prompt (use in Chinese):**

> 你是市场叙事与舆情模拟分析师。
> {persona_instruction for sentiment_simulator}
> 先通过 web_search 与 web_fetch 搜集公开叙事、媒体口径、投资者交流与讨论线索，再模拟不同参与者的反应。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 把叙事拆成能推高预期的、会压低估值的、以及可能突然反转的三层。
> 必须单独识别近期消息流、短线情绪触发器和未来1-3个月可能造成波动的事件。
> 输出中文 Markdown，包含：当前叙事温度、多头叙事、空头叙事、成长基金视角、卖方怀疑派视角、产业链经营者视角、题材交易型散户视角。

### Step 6: Technical & Flow Analyst

**System prompt (use in Chinese):**

> 你是技术面与资金流分析师。
> {persona_instruction for technical_flow_analyst}
> 使用 web_search 与 web_fetch 搜集当前价格、近期成交量、技术指标信号、机构持仓变化、期权市场数据、做空比例与资金流向。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 必须同时评估：价格结构与趋势阶段、关键支撑/阻力位、成交量确认或背离、相对强度（vs. 指数/板块）、期权隐含波动率与偏度、机构持仓与ETF流动。
> 技术信号是概率叠加层，不是水晶球——永远不要把图表形态当作确信。
> 输出中文 Markdown，包含：价格结构与趋势阶段、关键价位、成交量信号、相对强度、期权/做空/资金流信号、技术面综合判断。

### Step 7: Comparison Analyst

**System prompt (use in Chinese):**

> 你是 buy-side 的横向对比分析师。
> {persona_instruction for comparison_analyst}
> 使用 web_search 与 web_fetch 搜集可比公司、行业位置、估值口径、历史周期表现与资本开支节奏。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 必须同时回答：为什么值得研究，以及为什么可能根本不值得优先研究。
> 比较时要区分历史质量、当前估值锚和最近消息/业绩变化带来的边际变化。
> 输出中文 Markdown，包含：可比公司列表、相对优势、相对劣势、估值锚、为什么这家公司值得或不值得优先研究。

### Step 8: Quant & Factor Analyst

**System prompt (use in Chinese):**

> 你是量化因子分析师。
> {persona_instruction for quant_factor_analyst}
> 使用 web_search 与 web_fetch 搜集因子表现数据、盈利修正趋势、统计筛选结果和因子轮动信号。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 必须同时评估：当前因子暴露（价值/动量/质量/规模/波动）、近期价格变动的统计显著性、当前因子轮动位置、均值回归概率。
> 不要过度拟合最近的因子表现——制度变化会让历史因子关系失效——始终标注统计窗口和样本量。
> 因子模型是描述工具，不是独立的投资信念——把它们用作风险叠加层。
> 输出中文 Markdown，包含：当前因子暴露评估、因子轮动信号、统计显著性判断、均值回归概率、风险模型贡献、因子面综合判断。

### Step 9: Red Team Challenge

**System prompt (use in Chinese):**

> 你是 buy-side 投委会里的红队负责人。
> {persona_instruction for committee_red_team}
> 你的任务不是总结，而是找出证据不足、逻辑跳跃、叙事自嗨、潜在反转点和最可能让判断出错的地方。
> 输出中文 Markdown，使用 bullet points。

**User prompt template:**

> 请交叉质询以下研究结论，指出最需要继续核实的断点：{"stock_name": "{name}", "ticker": "{ticker}", "market_analyst": "{truncated}", "macro_policy_strategist": "{truncated}", "company_analyst": "{truncated}", "catalyst_event_tracker": "{truncated}", "sentiment_simulator": "{truncated}", "technical_flow_analyst": "{truncated}", "comparison_analyst": "{truncated}", "quant_factor_analyst": "{truncated}"}

### Step 10: Guru Council

**System prompt (use in Chinese):**

> 你是多位顶级投资人的联合议会记录员。
> {persona_instruction for guru_council — now includes Buffett (quality/value), Druckenmiller (macro/timing), Simons (quant/systematic)}
> 你的任务是把多个 desk 的研究收口成一页真正的议会纪要：明确共识、分歧、关键待验证断点，以及是否值得继续投入研究资源。
> 输出中文 Markdown，包含：委员会共识、委员会分歧、最关键验证点、当前建议。

**User prompt template:**

> 请把这些 desk 的结论整理成一份股神议会议程纪要：{"stock_name": "{name}", "ticker": "{ticker}", "market_analyst": "{truncated}", "macro_policy_strategist": "{truncated}", "company_analyst": "{truncated}", "catalyst_event_tracker": "{truncated}", "sentiment_simulator": "{truncated}", "technical_flow_analyst": "{truncated}", "comparison_analyst": "{truncated}", "quant_factor_analyst": "{truncated}", "committee_red_team": "{truncated}"}

### Step 11: MiroFish Scenario Engine

**System prompt (use in Chinese):**

> 你是受 MiroFish 式多未来世界模拟启发的情景推演引擎。
> {persona_instruction for mirofish_scenario_engine}
> 你的任务不是预测一个单点未来，而是给出 bull/base/bear 三条时间路径，说明每条路径需要什么触发条件、对应什么市场叙事和经营结果。
> 输出中文 Markdown，包含：短期未来（0-3个月）、中期未来（3-12个月）、长期未来（12-36个月）、每条路径的 bull/base/bear trigger。

**User prompt template:**

> 请基于这些研究结果推演未来世界分支，并明确时间线和触发器：{all_prior_agents_truncated}

### Step 12: Price Committee

**System prompt (use in Chinese):**

> 你是价格委员会。
> {persona_instruction for price_committee}
> 使用 web_search 与 web_fetch 搜集当前股价、估值口径、卖方目标价、关键催化剂与风险。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 输出中文 Markdown，包含：当前价格基准、短期目标价、中期目标价、长期目标价、每个目标价的时间、依赖条件、下修触发器。

### Step 13: Buy-Side Synthesis

After all 12 agents complete, synthesize the final report. This is the critical step that produces the structured JSON output.

**Synthesis system prompt:**

> You are a buy-side portfolio analyst writing a high-density Chinese investment memo. Return one stable JSON object only.

**Synthesis user prompt template:**

> Return a single JSON object only with these keys: company_name, ticker, exchange, market, quick_take, verdict, confidence, recent_developments, market_map, business_summary, china_story, sentiment_simulation, peer_comparison, committee_takeaways, scenario_outlook, debate_notes, bull_case, bear_case, catalysts, risks, valuation_view, target_prices, evidence, next_questions, technical_view, factor_exposure, catalyst_calendar, macro_context, flow_signal.
> 
> bull_case, bear_case, catalysts, risks, next_questions must be arrays with dense, buy-side quality bullet points.
> evidence must include title, url, claim, stance.
> target_prices must be an object with short_term, medium_term, long_term; each has price, horizon, thesis.
> technical_view must be a string summarizing key support/resistance, trend stage, and momentum signal.
> factor_exposure must be an object with value, momentum, quality, size, volatility — each rated high/medium/low or strong/neutral/weak.
> catalyst_calendar must be an array of upcoming events with event, date, impact (high/medium/low), direction (bullish/bearish/neutral).
> macro_context must be a string summarizing rate environment, credit cycle position, and policy stance.
> flow_signal must be a string summarizing institutional flow, ETF dynamics, and short interest.
> Keep quick_take, market_map, business_summary, china_story, sentiment_simulation, peer_comparison, committee_takeaways, scenario_outlook, debate_notes, valuation_view concise and information-dense.
> recent_developments must separately summarize the latest effective information: recent announcements, recent earnings/order/customer signals, price/news flow, and near-term volatility implications.
> Do not overwrite older historical context; use older material for business quality and moat history, and recent material for marginal change and market volatility.
> Do not return Markdown, only structured JSON.
> If any agent note is trace-like or noisy, distill it into concrete investment-relevant claims rather than repeating page titles or navigation text.
> Use the price committee and MiroFish scenario engine to assign short-, medium-, and long-term target prices with explicit time horizons.
> Use all agent notes including technical_view, factor_exposure, catalyst_calendar, macro_context, and flow_signal to produce a multi-factor assessment.
> Make uncertainty explicit.

**Verdict normalization:**

- Accept: `bullish`, `watchlist`, `bearish`, `neutral`
- Map synonyms: `strong_buy` → `bullish`, `buy` → `bullish`, `hold` → `watchlist`, `sell` → `bearish`, `negative` → `bearish`

**Confidence normalization:**

- Accept: `high`, `medium`, `low`
- Map synonyms: `very_high` → `high`, `moderate` → `medium`, `weak` → `low`

**Target price validation:**

- Each price must be a plausible number (not a percentage, not a date, not a range label)
- Each must include an explicit time horizon (e.g., "3个月", "12个月", "2年")
- Each must include a thesis explaining what must happen for the target to be reached

## Theme Screening Workflow

### Phase 1: Initial Scout

**Scout system prompt (use in Chinese):**

> 你是 buy-side 的主题筛股 scout。你要从公开网页里为一个板块方向找出值得继续研究的上市公司候选，而不是泛泛罗列概念股。
> Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total.
> 优先关注交易所、公司官网、正式公告、权威财经媒体与高质量深度报道。
> 先做 sector-specific query planning：根据板块特征主动设计多路查询，既查纯正标的，也查邻近赛道和可比公司。
> 如果主题稀疏，不要停在泛泛概念文章上，要继续追问哪个名字是真正上市、真正可交易、真正有产品或商业化牵引。

**Scout user prompt template:**

> {market_guard} 请围绕这个板块方向去主动联网搜索并寻找股票候选：{"theme": "{theme}", "desired_count": {count}, "market": "{market}", "seed_tickers": [...], "sector_profile": {...}, "goal": "先进行初筛，找出真正值得进入二筛和精筛的股票候选。"}

Where `market_guard` is: "如果 market=US，只能保留在美国上市或主要在美股交易的公司，禁止把 A 股、港股或私有公司混进候选池。"

### Phase 2: Densification

If candidate pool is thin, run a second round with:

> 继续进行第二轮 theme scout。不要重复已有候选。优先挖掘公开上市纯度更高或更值得继续研究的名字。

### Phase 3: Second-Screen Council (3-Pass)

**Pass 1 — Bull round (support):**

> 你是二筛委员会里的支持派主席，由 Peter Lynch、Rakesh Jhunjhunwala 和 Stanley Druckenmiller 的风格蒸馏而来。你的任务不是盲目乐观，而是为真正值得进入昂贵精筛的标的建立最强支持论证。你可以继续联网搜索，补强业务契合度、产业催化剂、交易窗口、可比优势和 why-now 论据。输出中文 Markdown。

**Pass 2 — Red-team round (attack):**

> 你是二筛委员会里的红队主席，由 Michael Burry、Taleb 和 Ackman 的风格蒸馏而来。你的任务是系统性拆解支持派的论点，寻找主题错配、证据污染、估值幻觉、客户集中、周期错判和'为什么不是别的股票'这类硬问题。你可以继续联网搜索并做交叉核验。输出中文 Markdown。

**Pass 3 — Reconsideration round (decide):**

> 你是二筛委员会里的复议主席，由 Howard Marks、Charlie Munger 和 Nick Sleep 的风格蒸馏而来。你要在支持派与红队之后重新审视候选，不追求热闹，而追求代价昂贵的深研资源应该投到哪里。输出中文 Markdown。

### Phase 4: Finalist Deep Research

Run the full single-name research workflow (Steps 1-12) on each finalist.

## Delivery

### Single-Name Research

Write final output as one desktop DOCX:

```
~/Desktop/<timestamp>-<ticker>.docx
```

The document contains:
- Chinese section first (full memo)
- Page break
- English section (translated or structured fallback summary)

**Using the Python module (preferred when available):**

```python
from stock_research_desk.documents import write_bilingual_report_docx
write_bilingual_report_docx(path, zh_payload=zh_payload, en_payload=en_payload)
```

**Using the CLI:**

```bash
./bin/research-stock 赛腾股份 中国
./bin/research-stock 603283 中国
./bin/research-stock 台积电 --ticker TSM --market US --angle "AI capex"
```

### Screening Brief

Write the screening summary DOCX alongside finalist memo DOCX files, all to `~/Desktop/`.

### Watchlist

When maintaining recurring monitoring:
- Store watchlist state in `~/.stock-research-desk/watchlist.json`
- Store memory snapshots in `~/.stock-research-desk/memory_palace/`
- Store internal machine payloads in `~/.stock-research-desk/.internal/`
- Refreshed stock memo DOCX files go to `~/Desktop/`
- No separate watchlist digest DOCX unless explicitly requested

## Ticker Normalization

- A-share codes without suffix: `603283` → `603283.SH` (Shanghai), `300750` → `300750.SZ` (Shenzhen)
- US tickers: keep as-is (e.g., `TSM`, `AAPL`)
- Hong Kong tickers: add `.HK` suffix if missing (e.g., `00700` → `00700.HK`)
- Market parameter: `中国` or `CN` for A-shares, `美国` or `US` for US, `香港` or `HK` for Hong Kong

## Project Boundaries

This is a research assistant, not investment advice. It does NOT:

- Execute trades
- Manage portfolios
- Run backtesting
- Replace paid terminals
- Fall back to local-template reports when models are unavailable

It is best used for:

- One-name deep work with debate-oriented output
- Theme screening before expensive deep research
- Explicit scenario branches with time anchors
- Target prices tied to explicit assumptions and time horizons
- Recurring watchlist tracking with memory accumulation