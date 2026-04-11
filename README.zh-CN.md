# Stock Research Desk

[English README](README.md)

![Stock Research Desk banner](assets/banner.svg)

`stock-research-desk` 是一个云端优先、终端优先的多 Agent 股票研究工作台。它面向单股深度研究、主题/板块筛选、watchlist 定期刷新、邮箱交互，以及 Codex Skill 模式。

它的目标不是替你自动交易，而是把一个股票代码、公司名或板块方向，变成一份更接近 buy-side memo 的研究文档：

- 证据源质量控制
- 市场与公司分析
- 多 Agent 交叉讨论
- 红队质疑与复议
- MiroFish 风格多未来场景
- 短期 / 中期 / 长期目标价，并明确时间区间
- 桌面只交付一个最终 DOCX，内部 JSON / memory / watchlist 状态隐藏保存

## 快速入口

- [项目展示页](docs/showcase.md)
- [示例研究 memo](docs/sample-memo.md)
- [赛腾股份案例](docs/case-study-saiteng.md)
- [示例筛选摘要](docs/sample-screening.md)
- [CLI 工作流](docs/cli-workflow.md)
- [Codex Skill 模式](docs/codex-skill.md)

## 它适合做什么

| 需求 | 推荐模式 | 交付 |
| --- | --- | --- |
| 单股深度研究 | 终端 CLI | 一个桌面 DOCX + 内部 JSON |
| 主题/板块候选筛选 | 终端 CLI | 筛选 DOCX + finalist memo |
| 定期跟踪 watchlist | watchlist + 邮箱 | 到期股票 memo + 内部队列状态 |
| 让 Codex 当主脑 | Codex Skill | 同样保持单 DOCX 交付 |

## 为什么值得收藏

- 它不是单次聊天，而是一条可重复运行的研究流程。
- 它把“初筛”和“深研”拆开，避免便宜候选发现伪装成高确信结论。
- 它保留分歧：红队、股神议会、场景引擎都会进入最终判断链路。
- 它的交付很干净：桌面只放最终 DOCX，机器状态放到隐藏工作区。
- 它明确不做交易、回测、组合管理，也不会在云端模型不可用时用本地模板伪装成真实报告。

## 60 秒上手

```bash
git clone https://github.com/wd041216-bit/stock-research-desk.git
cd stock-research-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

然后把你的 Ollama Cloud key 写入 `.env`：

```bash
OLLAMA_API_KEY=your_ollama_cloud_api_key
```

默认云端模型链是：

```text
glm-5.1:cloud -> kimi-k2.5:cloud -> qwen3.5:cloud
```

最简单的交互式启动：

```bash
./bin/research-stock
```

它会依次询问你要启动“单股分析”还是“主题/板块筛股”、市场/国家，以及具体股票或板块主题。

直接运行一份单股研究：

```bash
./bin/research-stock 赛腾股份 中国
```

也可以只输入 A 股代码和国家，不需要自己补 `.SH` / `.SZ`：

```bash
./bin/research-stock 603283 中国
```

默认会做综合 buy-side 研究，覆盖业务质量、最新动态、估值、催化、风险、舆情、同行对比、场景路径和目标价。只有当你明确想加特殊叙事时，才需要 `--angle`。

## 输出在哪里

默认用户可见交付：

- `~/Desktop/<timestamp>-<ticker>.docx`

这个 DOCX 里中文在前，英文另起一页，不再在桌面散落多个 watchlist 文件或 memory 文件。

内部状态默认放在：

- `~/.stock-research-desk/`

其中包含 memory palace、watchlist 队列、内部 JSON、邮箱状态等机器可读内容。

## 板块 / 主题筛选

```bash
./bin/research-stock screen "中国机器人" --market CN --count 3
```

筛选流程会分三层：

- 初筛：从公开网页线索中找候选公司
- 二筛：为候选生成 mini-dossier，并进行多阶段股神议会
- 精筛：对 finalist 跑完整单股深研流程

它不追求全市场扫描，也不接付费金融 API。它更像一个“不太在乎时间成本，但更在乎研究质量”的候选发现和深研工作流。

## Watchlist

```bash
./bin/research-stock watchlist add 赛腾股份 --market 中国 --interval 7d
./bin/research-stock watchlist run-due
```

watchlist 只在你显式添加并触发时运行。到期运行时，它会刷新对应股票 memo；队列、周期和历史状态保存在内部工作区，不会在桌面生成额外 watchlist digest 文件。

## 邮箱交互

可以用 QQ 邮箱或任何支持 IMAP / SMTP app password 的邮箱作为轻量命令入口。

```bash
export STOCK_RESEARCH_DESK_EMAIL_ADDRESS="your_mailbox@example.com"
export STOCK_RESEARCH_DESK_EMAIL_APP_PASSWORD="your_mailbox_app_password"
./bin/research-stock email run-once
```

支持的邮件主题示例：

- `research: 赛腾股份 |  | 中国`
- `screen: 中国机器人 | 3 | 中国`
- `watchlist add: 赛腾股份 |  | 7d | 中国`
- `watchlist list`
- `watchlist run-due`

回复会采用研究台格式，例如：

- `Single-Name Desk Note`
- `Screening Brief`
- `Morning Watchlist Brief`
- `Weekly Watchlist Wrap`

## Codex Skill 模式

仓库也内置了 Codex Skill：

- [`codex-skill/stock-research-desk/SKILL.md`](codex-skill/stock-research-desk/SKILL.md)

在 Codex-native 模式中：

- Codex 是主脑
- 优先使用 Codex 自己的联网搜索和页面读取
- 只有搜索或抓取明确报错时，才 fallback 到 `cross-validated-search`
- watchlist 更推荐交给 Codex automations
- 最终交付仍然保持一个桌面 DOCX

这是一个增量模式，不会替换默认 CLI。

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OLLAMA_API_KEY` | 必填 | Ollama Cloud API key |
| `STOCK_RESEARCH_DESK_HOME` | `~/.stock-research-desk` | 隐藏内部状态、memory、watchlist 和机器产物 |
| `STOCK_RESEARCH_DESK_MODEL` | `glm-5.1:cloud` | 默认研究模型 |
| `STOCK_RESEARCH_DESK_MODEL_FALLBACKS` | `glm-5.1:cloud,kimi-k2.5:cloud,qwen3.5:cloud` | 只走云端的 fallback 链 |
| `STOCK_RESEARCH_DESK_THINK` | `high` | 推理深度 |
| `STOCK_RESEARCH_DESK_MAX_RESULTS` | `5` | 每步最大搜索结果数 |
| `STOCK_RESEARCH_DESK_MAX_FETCHES` | `6` | 每步最大页面抓取数 |
| `STOCK_RESEARCH_DESK_TIMEOUT_SECONDS` | `45` | 单次模型调用超时 |
| `STOCK_RESEARCH_DESK_OLLAMA_HOST` | `https://ollama.com` | Ollama Cloud host |
| `STOCK_RESEARCH_DESK_EMAIL_PROVIDER` | `qq` | 邮箱预设 |

## 证据质量规则

它不会把所有网页结果一视同仁。当前 pipeline 会优先考虑：

- 交易所、监管披露、公告和 IR 页面
- 高质量财经媒体
- 与公司名、ticker 和主题强相关的页面
- 较新的公告、订单、业绩、行业催化与风险事件

它会惩罚或过滤：

- 论坛噪声
- 低内容量行情页
- 聚合站导航垃圾
- 与目标公司名称相似但实体不一致的页面

## 项目边界

这是研究助手，不是投资建议。

它不做：

- 自动交易
- 组合管理
- paper trading
- 回测主流程
- 付费终端替代
- 本地模型 fallback 到模板报告

它更适合：

- 单股深度研究
- 主题候选池筛选
- 多轮讨论和分歧保留
- 目标价与时间区间检查
- 反复跟踪同一个 watchlist

## 测试

```bash
source .venv/bin/activate
pytest -q
```

## 灵感来源

- investor-style analyst decomposition inspired by [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- multi-future branching inspired by [MiroFish](https://github.com/666ghj/MiroFish)
- runtime resilience influenced by the `openstream` design philosophy

## License

MIT
