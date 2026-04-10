import pytest
from pathlib import Path

from stock_research_desk.stock_cli import (
    agent_output_outline,
    build_agent_user_prompt,
    build_buy_side_synthesis_prompt,
    build_company_analyst_prompt,
    build_market_analyst_prompt,
    build_red_team_fallback,
    build_sentiment_simulator_prompt,
    build_comparison_fallback_from_evidence,
    build_sentiment_fallback_from_evidence,
    clean_research_summary,
    derive_target_prices_from_context,
    derive_role_bullets,
    choose_section_list,
    choose_section_text,
    distill_agent_note,
    evidence_signal_lines,
    extract_markdown_sections,
    extract_evidence_from_traces,
    extract_target_prices_from_text,
    load_config,
    load_memory_context,
    merge_evidence,
    normalize_confidence,
    normalize_evidence,
    normalize_report_payload,
    normalize_target_prices,
    normalize_ticker,
    normalize_verdict,
    render_markdown,
    render_agent_trace_summary,
    resolve_think,
    sanitize_source_text,
    save_memory_context,
    source_quality_score,
    should_replace_comparison_summary,
    should_replace_sentiment_summary,
    slugify,
    summarize_memory_context,
)


def test_slugify_keeps_chinese_and_strips_noise() -> None:
    assert slugify("赛腾股份 / 603283.SH") == "赛腾股份-603283-sh"


def test_normalize_evidence_drops_empty_rows() -> None:
    evidence = normalize_evidence(
        [
            {"title": "A", "url": "https://example.com", "claim": "x", "stance": "support"},
            {"title": "", "url": "", "claim": "", "stance": "neutral"},
        ]
    )
    assert len(evidence) == 1
    assert evidence[0]["title"] == "A"


def test_extract_evidence_from_traces_reads_search_and_fetch_results() -> None:
    traces = [
        [
            {
                "tool_name": "web_search",
                "arguments": {"query": "赛腾股份 客户"},
                "result": {
                    "results": [
                        {"title": "Investor page", "url": "https://example.com/ir", "content": "公告与业务摘要"},
                    ]
                },
            },
            {
                "tool_name": "web_fetch",
                "arguments": {"url": "https://example.com/filing"},
                "result": {"url": "https://example.com/filing", "title": "Filing", "excerpt": "订单与收入信号"},
            },
        ]
    ]
    evidence = extract_evidence_from_traces(traces)
    assert len(evidence) == 2
    assert evidence[0]["url"] == "https://example.com/ir"
    assert evidence[1]["title"] == "Filing"


def test_extract_evidence_from_traces_prefers_higher_quality_domains() -> None:
    traces = [
        [
            {
                "tool_name": "web_search",
                "arguments": {"query": "赛腾股份 公告"},
                "result": {
                    "results": [
                        {"title": "股吧讨论", "url": "https://guba.eastmoney.com/test", "content": "情绪噪音"},
                        {"title": "公司公告", "url": "https://www.cninfo.com.cn/test", "content": "正式公告摘要"},
                    ]
                },
            }
        ]
    ]
    evidence = extract_evidence_from_traces(traces)
    assert len(evidence) == 1
    assert evidence[0]["url"] == "https://www.cninfo.com.cn/test"
    assert int(evidence[0]["quality"]) >= 90


def test_sanitize_source_text_drops_navigation_noise() -> None:
    text = """
    谢谢您的宝贵意见
    同花顺F10
    赛腾股份是智能制造装备公司
    半导体设备与消费电子自动化是核心方向
    换肤
    """
    cleaned = sanitize_source_text(text)
    assert "谢谢您的宝贵意见" not in cleaned
    assert "换肤" not in cleaned
    assert "智能制造装备公司" in cleaned


def test_distill_agent_note_extracts_company_sections() -> None:
    content = """
### 业务概览
- 公司从消费电子自动化切入半导体设备。
### 客户与订单
- 核心客户导入仍在推进。
### 多头逻辑
- 半导体国产替代带来弹性。
### 空头逻辑
- 客户集中度仍高。
### 催化剂
- 新客户导入。
### 主要风险
- 订单持续性不稳。
"""
    distilled = distill_agent_note(name="company_analyst", content=content, tool_traces=[])
    assert "消费电子自动化" in distilled["summary"]
    assert "核心客户导入仍在推进" in distilled["summary"]
    assert distilled["bull_case"][0] == "半导体国产替代带来弹性。"
    assert distilled["risks"][0] == "订单持续性不稳。"


def test_extract_markdown_sections_collects_multiple_headings() -> None:
    content = """
## 业务概览
- 公司主营自动化设备。
## 客户与订单
- 苹果链客户仍是核心。
## 财务与经营信号
- 毛利率维持高位。
"""
    section = extract_markdown_sections(content, "业务概览", "客户与订单", "财务与经营信号")
    assert "公司主营自动化设备。" in section
    assert "苹果链客户仍是核心。" in section
    assert "毛利率维持高位。" in section


def test_clean_research_summary_drops_title_noise() -> None:
    summary = clean_research_summary(
        """
        赛腾股份2024年报|赛腾股份_新浪财经_新浪网
        股票| 主板 必读 研报 新股 创业板
        公司从消费电子自动化切入半导体量检测设备。
        半导体国产替代仍是多头主线。
        """
    )
    assert "新浪财经" not in summary
    assert "公司从消费电子自动化切入半导体量检测设备。" in summary
    assert "半导体国产替代仍是多头主线。" in summary


def test_distill_red_team_prefers_cleaned_section_over_raw_blob() -> None:
    content = """
- 最关键的断点是苹果依赖是否真正下降。
```markdown
## 市场结构
- 消费电子业务仍占大头，半导体故事尚未完成收入迁移。
## 待核实问题
- 需要核实前五大客户集中度。
```
"""
    distilled = distill_agent_note(name="committee_red_team", content=content, tool_traces=[])
    assert "苹果依赖" in distilled["summary"] or "消费电子业务仍占大头" in distilled["summary"]
    assert "```" not in distilled["summary"]


def test_evidence_signal_lines_strip_site_suffixes_and_noise() -> None:
    traces = [
        {
            "tool_name": "web_search",
            "arguments": {"query": "赛腾股份 半导体 订单"},
            "result": {
                "results": [
                    {
                        "title": "赛腾股份2024年报|赛腾股份_新浪财经_新浪网",
                        "url": "https://example.com/a",
                        "content": "股票| 主板 必读 研报 新股 创业板\n半导体量测设备加速国产替代，订单改善仍待验证。",
                    }
                ]
            },
        }
    ]
    signals = evidence_signal_lines(traces)
    assert any("半导体量测设备加速国产替代" in item for item in signals)
    assert not any("主板 必读" in item for item in signals)


def test_derive_role_bullets_builds_company_risk_and_catalyst_lists() -> None:
    signals = [
        "半导体设备收入占比提升，国产替代逻辑继续增强。",
        "客户集中度仍高，订单持续性存在不确定。",
        "苹果创新周期回暖可能带来订单改善。",
    ]
    risks = derive_role_bullets("risk", signals)
    catalysts = derive_role_bullets("catalyst", signals)
    assert any("客户集中度" in item for item in risks)
    assert any("订单改善" in item for item in catalysts)


def test_build_sentiment_fallback_from_evidence_creates_four_view_summary() -> None:
    text = build_sentiment_fallback_from_evidence(
        [
            "半导体国产替代逻辑继续增强。",
            "客户集中度仍高，订单持续性存在不确定。",
            "苹果新品周期回暖可能带来订单改善。",
        ]
    )
    assert "成长资金" in text
    assert "卖方怀疑派" in text
    assert "订单改善" in text


def test_build_comparison_fallback_from_evidence_mentions_peers_and_gaps() -> None:
    text = build_comparison_fallback_from_evidence(
        [
            "中科飞测在量检测设备领域已形成更强卡位。",
            "赛腾的半导体量测设备收入占比仍待验证。",
            "客户集中度仍高，订单持续性存在不确定。",
        ]
    )
    assert "中科飞测" in text
    assert "短板" in text or "风险" in text


def test_should_replace_sentiment_summary_when_missing_role_views() -> None:
    assert should_replace_sentiment_summary("赛腾股份2024年报点评：半导体量测设备加速国产替代") is True
    assert should_replace_sentiment_summary("成长资金更愿意交易国产替代，卖方怀疑派则盯住客户集中度。") is False


def test_should_replace_comparison_summary_when_no_peer_or_valuation_language() -> None:
    assert should_replace_comparison_summary("赛腾股份2024年度财务报表及审计报告") is True
    assert should_replace_comparison_summary("与中科飞测相比，赛腾的估值锚和客户验证仍偏弱。") is False


def test_merge_evidence_keeps_primary_then_unique_fallback() -> None:
    primary = [{"title": "A", "url": "https://example.com/a", "claim": "x", "stance": "support"}]
    fallback = [
        {"title": "A", "url": "https://example.com/a", "claim": "x", "stance": "support"},
        {"title": "B", "url": "https://example.com/b", "claim": "y", "stance": "neutral"},
    ]
    merged = merge_evidence(primary, fallback)
    assert [item["title"] for item in merged] == ["A", "B"]


def test_normalize_report_payload_fills_defaults_and_uses_fallback_evidence() -> None:
    payload = normalize_report_payload(
        {"company_name": "赛腾股份", "evidence": []},
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        model="glm-5:cloud",
        fallback_evidence=[{"title": "Source", "url": "https://example.com", "claim": "示例", "stance": "neutral"}],
        distilled_notes={"company_analyst": {"summary": "更像研究摘要。", "bull_case": ["A"], "bear_case": ["B"], "catalysts": ["C"], "risks": ["D"]}},
    )
    assert payload["ticker"] == "603283.SH"
    assert payload["verdict"] == "watchlist"
    assert payload["evidence"][0]["title"] == "Source"
    assert "report_markdown" in payload


def test_render_markdown_includes_multi_agent_sections() -> None:
    markdown = render_markdown(
        company_name="赛腾股份",
        ticker="603283.SH",
        exchange="SSE",
        market="CN",
        model="glm-5:cloud",
        quick_take="需要继续补证。",
        verdict="watchlist",
        confidence="medium",
        market_map="行业景气度与资本开支节奏仍需判断。",
        business_summary="自动化设备公司。",
        china_story="受益于国内高端制造升级。",
        sentiment_simulation="市场预期分化较大。",
        peer_comparison="与可比公司相比仍需验证估值锚。",
        committee_takeaways="委员会倾向先维持 watchlist。",
        scenario_outlook="Bull/base/bear 三条路径仍围绕订单验证展开。",
        debate_notes="客户集中与订单持续性需要红队继续质询。",
        bull_case=["国产替代"],
        bear_case=["客户集中"],
        catalysts=["订单加速"],
        risks=["资本开支波动"],
        valuation_view="缺少一致估值锚。",
        target_prices=normalize_target_prices(
            {
                "short_term": {"price": "42", "horizon": "3个月", "thesis": "订单验证"},
                "medium_term": {"price": "50", "horizon": "12个月", "thesis": "收入结构升级"},
                "long_term": {"price": "63", "horizon": "24个月", "thesis": "重估为高质量设备资产"},
            },
            None,
        ),
        evidence=[{"title": "Source", "url": "https://example.com", "claim": "示例", "stance": "support"}],
        next_questions=["订单结构是否改善"],
    )
    assert "# 赛腾股份 研究备忘录" in markdown
    assert "## 市场与行业图谱" in markdown
    assert "## 舆情与叙事模拟" in markdown
    assert "## 股神议会纪要" in markdown
    assert "## MiroFish 多未来场景" in markdown
    assert "## 目标价与时间框架" in markdown
    assert "## 证据清单" in markdown


def test_load_config_rejects_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("STOCK_RESEARCH_DESK_OLLAMA_HOST", "http://127.0.0.1:11434")
    with pytest.raises(RuntimeError, match="Cloud only"):
        load_config(
            model="glm-5:cloud",
            think="low",
            max_results=4,
            max_fetches=4,
            timeout_seconds=45,
            output_dir="reports",
        )


def test_resolve_think_disables_gemini_tool_phase() -> None:
    assert resolve_think("gemini-3-flash-preview", "medium") is None


def test_resolve_think_keeps_glm_setting() -> None:
    assert resolve_think("glm-5:cloud", "medium") == "medium"


def test_agent_prompts_include_stock_and_objective() -> None:
    user_prompt = build_agent_user_prompt(
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        objective="分析业务质量",
    )
    assert "赛腾股份" in user_prompt
    assert "603283.SH" in user_prompt
    assert "分析业务质量" in user_prompt


def test_memory_context_is_summarized_into_prompt() -> None:
    class FakeMemory:
        payload = {
            "verdict": "watchlist",
            "confidence": "medium",
            "bull_case": ["国产替代"],
            "bear_case": ["客户集中"],
            "next_questions": ["订单持续性？"],
            "evidence_digest": ["公告：订单改善"],
            "updated_at": "2026-04-10T00:00:00+00:00",
        }

    user_prompt = build_agent_user_prompt(
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        objective="分析业务质量",
        memory_context=FakeMemory(),
    )
    assert "watchlist" in user_prompt
    assert "订单持续性" in user_prompt


def test_role_prompts_reference_tools_and_dense_outputs() -> None:
    market_prompt = build_market_analyst_prompt(4, 4)
    company_prompt = build_company_analyst_prompt(4, 4)
    sentiment_prompt = build_sentiment_simulator_prompt(4, 4)

    assert "web_search" in market_prompt
    assert "Stanley Druckenmiller" in market_prompt
    assert "web_fetch" in company_prompt
    assert "Warren Buffett" in company_prompt
    assert "成长基金视角" in sentiment_prompt
    assert "Cathie Wood" in sentiment_prompt


def test_agent_output_outline_covers_company_and_sentiment_roles() -> None:
    assert "客户与订单" in agent_output_outline("company_analyst")
    assert "卖方怀疑派视角" in agent_output_outline("sentiment_simulator")


def test_render_agent_trace_summary_structures_company_fallback() -> None:
    traces = [
        {
            "tool_name": "web_search",
            "arguments": {"query": "赛腾股份 订单 客户"},
            "result": {
                "results": [
                    {"title": "A", "url": "https://example.com/a", "content": "订单改善，客户导入推进"},
                    {"title": "B", "url": "https://example.com/b", "content": "客户集中仍是主要风险，业绩下滑压力仍在"},
                ]
            },
        }
    ]
    text = render_agent_trace_summary(name="company_analyst", tool_traces=traces)
    assert "## 多头逻辑" in text
    assert "## 空头逻辑" in text
    assert "订单改善" in text


def test_build_red_team_fallback_produces_actionable_dissent() -> None:
    class FakeResult:
        def __init__(self, name: str, content: str) -> None:
            self.name = name
            self.content = content
            self.tool_traces = []

    note = build_red_team_fallback(
        market_analyst=FakeResult("market_analyst", "行业景气仍有波动，估值锚不清晰"),
        company_analyst=FakeResult("company_analyst", "客户集中度高，订单改善仍不足以证明持续性"),
        sentiment_simulator=FakeResult("sentiment_simulator", "市场叙事很热，但基本面验证仍不足"),
        comparison_analyst=FakeResult("comparison_analyst", "可比公司不足，估值判断容易失真"),
    )
    assert "不应把 watchlist 误判成 high conviction" in note
    assert "客户集中度" in note


def test_synthesis_prompt_requires_dense_buy_side_fields() -> None:
    class FakeResult:
        def __init__(self, name: str, content: str) -> None:
            self.name = name
            self.content = content
            self.tool_traces = [{"tool_name": "web_search"}]

    prompt = build_buy_side_synthesis_prompt(
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        market_analyst=FakeResult("market_analyst", "市场结论"),
        company_analyst=FakeResult("company_analyst", "公司结论"),
        sentiment_simulator=FakeResult("sentiment_simulator", "情绪结论"),
        comparison_analyst=FakeResult("comparison_analyst", "对比结论"),
        committee_red_team=FakeResult("committee_red_team", "红队质询"),
        guru_council=FakeResult("guru_council", "议会共识"),
        mirofish_scenario_engine=FakeResult("mirofish_scenario_engine", "三种未来路径"),
        price_committee=FakeResult("price_committee", "短期目标价：42元（3个月）"),
        distilled_notes={"company_analyst": {"summary": "更干净的公司摘要"}},
    )
    assert "Do not return Markdown, only structured JSON." in prompt
    assert "bull_case" in prompt
    assert "sentiment_simulation" in prompt
    assert "peer_comparison" in prompt
    assert "debate_notes" in prompt
    assert "committee_takeaways" in prompt
    assert "scenario_outlook" in prompt
    assert "target_prices" in prompt
    assert "distilled_notes" in prompt


def test_normalize_verdict_maps_freeform_labels() -> None:
    assert normalize_verdict("谨慎乐观") == "high_conviction"
    assert normalize_verdict("回避") == "reject"
    assert normalize_verdict("继续观察") == "watchlist"


def test_normalize_confidence_maps_numeric_and_chinese_labels() -> None:
    assert normalize_confidence("4") == "high"
    assert normalize_confidence("中等") == "medium"
    assert normalize_confidence("低") == "low"


def test_normalize_ticker_adds_china_suffix_from_exchange() -> None:
    assert normalize_ticker("603283", "SSE", "CN") == "603283.SH"


def test_choose_section_text_prefers_distilled_summary_for_low_quality_text() -> None:
    raw = "赛腾股份(603283)_公司公告_新浪财经_新浪网\n同花顺F10"
    chosen = choose_section_text(raw, "真正的研究摘要", "默认值")
    assert chosen == "真正的研究摘要"


def test_choose_section_list_rejects_title_like_singletons() -> None:
    chosen = choose_section_list(["赛腾股份(603283)_公司公告_新浪财经_新浪网"], ["真实要点"])
    assert chosen == ["真实要点"]


def test_save_and_load_memory_context_round_trip(tmp_path: Path) -> None:
    class FakeResult:
        def __init__(self, name: str, content: str) -> None:
            self.name = name
            self.content = content
            self.tool_traces = []

    memory_path = save_memory_context(
        memory_dir=tmp_path,
        stock_name="赛腾股份",
        normalized={
            "ticker": "603283.SH",
            "verdict": "watchlist",
            "confidence": "medium",
            "bull_case": ["国产替代"],
            "bear_case": ["客户集中"],
            "catalysts": ["订单改善"],
            "risks": ["景气波动"],
            "target_prices": {"short_term": {"price": "42", "horizon": "3个月", "thesis": "订单验证"}},
            "next_questions": ["订单持续性？"],
            "evidence": [{"title": "公告", "claim": "订单改善"}],
        },
        market_analyst=FakeResult("market_analyst", "行业结论"),
        company_analyst=FakeResult("company_analyst", "公司结论"),
        sentiment_simulator=FakeResult("sentiment_simulator", "叙事情绪"),
        comparison_analyst=FakeResult("comparison_analyst", "横向对比"),
        committee_red_team=FakeResult("committee_red_team", "红队质询"),
        guru_council=FakeResult("guru_council", "委员会共识"),
        mirofish_scenario_engine=FakeResult("mirofish_scenario_engine", "Bull/base/bear"),
        price_committee=FakeResult("price_committee", "短期目标价：42元（3个月）"),
    )
    loaded = load_memory_context(memory_dir=tmp_path, stock_name="赛腾股份", ticker="603283.SH")
    assert memory_path.exists()
    assert loaded is not None
    summary = summarize_memory_context(loaded)
    assert summary is not None
    assert summary["last_verdict"] == "watchlist"
    assert loaded.payload["persona_pack"]["committee_red_team"][0] == "Michael Burry"
    assert summary["key_bull_points"] == ["国产替代"]


def test_extract_target_prices_from_text_reads_price_horizon_and_thesis() -> None:
    payload = extract_target_prices_from_text(
        """
        - 短期目标价：42元，未来3个月，依据：订单验证与主题资金回流。
        - 中期目标价：50元，未来12个月，依据：收入结构升级与估值锚上修。
        - 长期目标价：63元，未来24个月，依据：重估为更高质量设备资产。
        """
    )
    assert payload["short_term"]["price"] == "42"
    assert "3个月" in payload["short_term"]["horizon"]
    assert "订单验证" in payload["short_term"]["thesis"]


def test_source_quality_score_prefers_official_domains() -> None:
    assert source_quality_score("https://www.cninfo.com.cn/test") > source_quality_score("https://finance.sina.com.cn/test")


def test_derive_target_prices_from_context_builds_numeric_fallbacks() -> None:
    payload = derive_target_prices_from_context(
        "当前价格基准：47.64元，估值仍待验证。",
        verdict="watchlist",
    )
    assert payload["short_term"]["price"]
    assert payload["medium_term"]["price"]
    assert payload["long_term"]["price"]
