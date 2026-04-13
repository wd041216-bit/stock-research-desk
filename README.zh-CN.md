# Stock Research Desk

[English](README.md)

![Stock Research Desk banner](assets/banner.svg)

12代理多因子股票研究台——单股深度研究、主题筛选、定期观察清单、中英双语文档交付。

## 为什么不同

大多数AI股票工具止步于搜索聚合或备忘录生成。本仓库将它们叠加为一个**辩论驱动工作流**：

- **12个专业分析师台**顺序运行，每个在前置分析基础上构建
- **多因子覆盖**：宏观、政策、催化、情绪、技术流、量化因子——不仅仅是基本面
- **红队质询**在结论形成前强制引入反面意见
- **大师议会**（巴菲特/德uckenmiller/西蒙斯）从三种截然不同的投资哲学综合
- **MiroFish情景引擎**投影牛市/基准/熊市三条路径，附带明确触发器和时间范围
- **目标价格**始终锚定明确的时间范围和投资逻辑，绝不凭空而来

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

## 使用模式

| 需求 | 模式 | 输出 |
| --- | --- | --- |
| 单股深度研究备忘录 | 终端CLI | 单个桌面DOCX |
| 主题筛选后再深度研究 | 终端CLI | 筛选DOCX + 决赛备忘录 |
| 自动定期刷新 | 观察清单 + 邮箱 | 刷新的股票备忘录 |

## 60秒启动

```bash
git clone https://github.com/wd041216-bit/stock-research-desk.git
cd stock-research-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# 在 .env 中填入你的 Ollama Cloud API Key
./bin/research-stock 赛腾股份 中国
```

Claude Code 集成请查看 [`claude-code-skill` 分支](https://github.com/wd041216-bit/stock-research-desk/tree/claude-code-skill)，包含完整的12代理提示模板、来源质量规则和中英双语DOCX交付说明。

## 分支

| 分支 | 用途 |
| --- | --- |
| `main` | 纯 agentic workflow — Python CLI 引擎，12代理管线 |
| `claude-code-skill` | Claude Code 技能版本 — SKILL.md、提示词、工作流参考 |

## 主题筛选

```bash
./bin/research-stock screen "中国机器人" --market CN --count 3
```

三层筛选：初筛 → 二筛大师议会 → 决赛深度研究。

## 观察清单

```bash
./bin/research-stock watchlist add 赛腾股份 --market 中国 --interval 7d
./bin/research-stock watchlist run-due
```

## 邮箱交互

```bash
export STOCK_RESEARCH_DESK_EMAIL_ADDRESS="your_mailbox@example.com"
export STOCK_RESEARCH_DESK_EMAIL_APP_PASSWORD="your_app_password"
./bin/research-stock email run-once
```

## 配置

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `OLLAMA_API_KEY` | 必需 | Ollama Cloud API密钥（CLI模式） |
| `STOCK_RESEARCH_DESK_HOME` | `~/.stock-research-desk` | 内部状态目录 |
| `STOCK_RESEARCH_DESK_MODEL` | `glm-5.1:cloud` | 默认模型（CLI模式） |
| `STOCK_RESEARCH_DESK_OUTPUT_DIR` | `reports` | 桌面交付目录 |
| `STOCK_RESEARCH_DESK_EMAIL_PROVIDER` | `qq` | 邮箱预设 |

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

## 测试

```bash
source .venv/bin/activate
pytest -q
```

112个测试覆盖代理提示构建、管线流程、归一化、DOCX生成和CLI命令。

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

## 这不是什么

- 不执行交易
- 不管理投资组合
- 不做回测
- 不做本地模板回退假装完成

## 灵感来源

- 投资者风格分析师分解灵感来自 [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- 多未来分支灵感来自 [MiroFish](https://github.com/666ghj/MiroFish)
- 运行时弹性受 `openstream` 设计哲学影响

## 许可证

MIT