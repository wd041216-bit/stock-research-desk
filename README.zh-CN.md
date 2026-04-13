# Stock Research Desk — Claude Code 技能分支

[English](README.md)

![Stock Research Desk banner](assets/banner.svg)

这是 [stock-research-desk](https://github.com/wd041216-bit/stock-research-desk) 的 **Claude Code 技能分支**。包含完整的技能清单、12代理提示模板、来源质量规则和工作流参考，可直接在 Claude Code 中运行12代理多因子股票研究管线。

纯 Python CLI agentic workflow 请查看 [`main` 分支](https://github.com/wd041216-bit/stock-research-desk/tree/main)。

## 本分支额外内容

在 `main` 分支核心 Python 引擎之上，本分支提供：

- `claude-skill/stock-research-desk/SKILL.md` — 完整技能清单，12代理提示词、证据规则和 DOCX 输出模式
- `claude-skill/stock-research-desk/agents/claude.yaml` — 12代理人格配置
- `claude-skill/stock-research-desk/references/workflow.md` — 详细12步管线参考
- `claude-skill/stock-research-desk/references/prompts.md` — 全部12代理的提示模板
- `claude-skill/stock-research-desk/references/repo-map.md` — 项目文件结构
- `claude-skill/stock-research-desk/references/watchlist-automation.md` — 观察清单调度

## 12代理管线

| 步骤 | 代理 | 搜索? | 聚焦 |
|------|------|--------|------|
| 1 | market_analyst | 是 | 宏观周期、行业结构、中国叙事 |
| 2 | macro_policy_strategist | 是 | 利率、信用周期、政策传导 |
| 3 | company_analyst | 是 | 业务质量、管理层、财务 |
| 4 | catalyst_event_tracker | 是 | 财报日期、内部人活动、并购、监管 |
| 5 | sentiment_simulator | 是 | 叙事温度、参与者心理 |
| 6 | technical_flow_analyst | 是 | 价格走势、成交量、机构流向、期权 |
| 7 | comparison_analyst | 是 | 同行比较、相对估值锚 |
| 8 | quant_factor_analyst | 是 | 因子暴露、统计显著性、制度 |
| 9 | committee_red_team | 否 | 反面质询、隐藏脆弱性 |
| 10 | guru_council | 否 | 多视角综合（巴菲特/德uckenmiller/西蒙斯） |
| 11 | mirofish_scenario_engine | 否 | 牛/基/熊情景投影 |
| 12 | price_committee | 是 | 带明确时间范围的目标价格 |

## 输出字段

每份报告包含以下全部字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| quick_take | 字符串 | 一段话结论与仓位建议 |
| verdict | 字符串 | bullish / bearish / watchlist / neutral |
| confidence | 字符串 | high / medium / low |
| business_summary | 字符串 | 业务模式、护城河、关键信号 |
| market_map | 字符串 | 行业结构、需求周期、竞争格局 |
| china_story | 字符串 | 中国叙事——需求、政策、地缘角度 |
| macro_context | 字符串 | 利率环境、信用周期、政策立场 |
| flow_signal | 字符串 | 机构流向、ETF动态、做空比例 |
| sentiment_simulation | 字符串 | 叙事温度、参与者心理 |
| peer_comparison | 字符串 | 相对估值、为什么选这个而非同行 |
| technical_view | 字符串 | 支撑/阻力、趋势阶段、动量信号 |
| factor_exposure | 表格 | 价值/动量/质量/规模/波动 评级 |
| catalyst_calendar | 表格 | 即将到来的事件：日期、影响、方向 |
| committee_takeaways | 字符串 | 大师议会共识与分歧 |
| debate_notes | 字符串 | 红队质询要点 |
| bull_case | 列表 | 3-5条看多理由 |
| bear_case | 列表 | 3-5条看空理由 |
| catalysts | 列表 | 3-5个催化事件 |
| risks | 列表 | 3-5个风险因素 |
| valuation_view | 字符串 | 估值锚与框架 |
| scenario_outlook | 字符串 | 牛/基/熊路径及触发器 |
| target_prices | 表格 | 短/中/长期目标价、时间范围、投资逻辑 |
| evidence | 表格 | 标题、URL、论点、立场、质量评分 |
| next_questions | 列表 | 3-5个待验证问题 |

## 快速使用

**单股研究：**
```
Research {stock_name} in {market}
```

**主题筛选：**
```
Screen the {theme} sector in {market}, find {count} finalists
```

**观察清单：**
```
Add {stock_name} to the watchlist with {interval} refresh cycle
```

## 作为 Claude Code 技能使用

1. 将技能清单安装到你的 Claude Code 配置中
2. 技能将引导 Claude Code 通过12代理管线，使用联网搜索和页面抓取
3. 输出为桌面上一个中英双语 DOCX 文件

## 分支

| 分支 | 用途 |
| --- | --- |
| `main` | 纯 agentic workflow — Python CLI 引擎，12代理管线 |
| `claude-code-skill` | 本分支 — Claude Code 技能版本，包含 SKILL.md、提示词和工作流参考 |

## 核心源文件（与 main 共享）

| 文件 | 用途 |
|------|------|
| `src/stock_research_desk/stock_cli.py` | 主 CLI、代理、筛选、邮箱、观察清单（12代理管线） |
| `src/stock_research_desk/documents.py` | DOCX 生成（双语，含多因子章节） |
| `src/stock_research_desk/persona_pack.py` | 12个投资者人格混合 |
| `src/stock_research_desk/runtime.py` | JSON 解析与修复 |

## 来源质量模型

基于域名级别的来源评分：

| 域名 | 分数 | 类别 |
|------|------|------|
| cninfo.com.cn | 96 | 官方公告 |
| sse.com.cn / szse.cn / hkexnews.hk | 95 | 交易所 |
| sec.gov | 94 | 官方公告 |
| yicai.com / caixin.com | 84 | 优质媒体 |
| eastmoney.com | 74 | 聚合器 |
| guba.eastmoney.com | 28（已屏蔽） | 论坛噪音 |

评分低于36的来源将被完全过滤。

## 验证结果

6股严格CEO评分（阈值：90/100）：

| 股票 | 评分 | 结果 |
|------|------|------|
| Microsoft (MSFT) | 92/100 | 通过 |
| Alphabet (GOOGL) | 93/100 | 通过 |
| Tesla (TSLA) | 92/100 | 通过（从89分优化） |
| ClearPoint Neuro (CLPT) | 91/100 | 通过（从87分优化） |
| 赛腾股份 (603283.SH) | 90/100 | 通过 |
| 人工智能ETF (515070) | 93/100 | 通过（从88分优化） |

## 测试

```bash
source .venv/bin/activate
pytest -q
```

112个测试覆盖代理提示构建、管线流程、归一化、DOCX生成和CLI命令。

## 灵感来源

- 投资者风格分析师分解灵感来自 [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- 多未来分支灵感来自 [MiroFish](https://github.com/666ghj/MiroFish)
- 运行时弹性受 `openstream` 设计哲学影响

## 许可证

MIT