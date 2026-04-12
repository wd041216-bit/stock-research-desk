from datetime import datetime
import os
from pathlib import Path

import pytest

from stock_research_desk.documents import (
    build_english_report_fallback,
    write_bilingual_report_docx,
    write_report_docx,
)
from stock_research_desk.stock_cli import (
    add_watchlist_entry,
    agent_output_outline,
    build_cloud_model_chain,
    build_interactive_command_args,
    build_screening_fallback_candidates,
    build_report_document_paths,
    build_seed_candidates,
    build_watchlist_digest_document_paths,
    combine_candidate_lists,
    build_agent_user_prompt,
    build_buy_side_synthesis_prompt,
    build_company_analyst_prompt,
    build_market_analyst_prompt,
    build_red_team_fallback,
    default_workspace_home,
    load_watchlist,
    parse_email_command,
    perform_fetch_with_fallback,
    perform_search_with_fallback,
    render_email_research_reply,
    render_email_screen_reply,
    render_screening_markdown,
    normalize_screen_candidates,
    parse_interval_hours,
    build_sentiment_simulator_prompt,
    build_screening_council_bull_prompt,
    build_screening_council_red_prompt,
    build_screening_council_reconsider_prompt,
    build_second_screen_prompt,
    build_comparison_fallback_from_evidence,
    build_sentiment_fallback_from_evidence,
    clean_research_summary,
    chat_with_guard,
    desk_briefing_mode,
    derive_target_prices_from_context,
    derive_role_bullets,
    choose_section_list,
    choose_section_text,
    distill_agent_note,
    evidence_signal_lines,
    evidence_freshness_score,
    extract_markdown_sections,
    extract_source_date,
    extract_evidence_from_traces,
    extract_target_prices_from_text,
    load_config,
    load_local_env_file,
    load_memory_context,
    main,
    merge_evidence,
    merge_screen_candidates,
    merge_seed_candidates,
    normalize_confidence,
    normalize_cloud_model_name,
    normalize_evidence,
    normalize_market_hint,
    normalize_report_payload,
    normalize_target_prices,
    normalize_ticker,
    normalize_verdict,
    format_target_price_snapshot,
    fetch_company_name_from_ticker,
    derive_company_identity,
    default_sector_query_axes,
    default_desktop_delivery_dir,
    is_market_compatible_candidate,
    looks_like_us_ticker,
    sector_profile_for,
    render_markdown,
    render_agent_trace_summary,
    resolve_research_request,
    resolve_think,
    sanitize_source_text,
    save_memory_context,
    save_watchlist,
    source_quality_score,
    should_replace_comparison_summary,
    should_replace_sentiment_summary,
    slugify,
    summarize_memory_context,
    remove_watchlist_entry,
    resolve_workspace_paths,
    run_due_watchlist,
    render_watchlist_digest_markdown,
    render_email_watchlist_digest_reply,
    render_email_watchlist_roster_reply,
    resolve_stock_name,
    unique_attachment_paths,
)


def test_slugify_keeps_chinese_and_strips_noise() -> None:
    assert slugify("赛腾股份 / 603283.SH") == "赛腾股份-603283-sh"


def test_write_report_docx_creates_a_docx_file(tmp_path: Path) -> None:
    output = tmp_path / "report.docx"
    payload = {
        "company_name": "SaiTeng",
        "ticker": "603283.SH",
        "exchange": "SSE",
        "market": "CN",
        "model": "kimi-k2.5:cloud",
        "quick_take": "Watchlist until order quality improves.",
        "verdict": "watchlist",
        "confidence": "high",
        "market_map": "Automation demand is stabilizing.",
        "business_summary": "The company sells automation equipment.",
        "china_story": "Industrial upgrade remains relevant.",
        "sentiment_simulation": "Narratives are improving but still mixed.",
        "peer_comparison": "Peers do not yet provide a clean valuation anchor.",
        "committee_takeaways": "Council wants better proof on customer quality.",
        "scenario_outlook": "Base case remains watchlist.",
        "debate_notes": "Red team is focused on customer concentration.",
        "valuation_view": "Valuation still needs cleaner anchors.",
        "bull_case": ["Operating leverage if semicap mix improves."],
        "bear_case": ["Customer concentration remains elevated."],
        "catalysts": ["New customer wins."],
        "risks": ["Narrative outruns fundamentals."],
        "next_questions": ["How durable is the order mix?"],
        "evidence": [{"title": "Example", "url": "https://example.com", "claim": "Example claim", "stance": "support"}],
        "target_prices": {
            "short_term": {"price": "45.00", "horizon": "1-3 months", "thesis": "Near-term validation."},
            "medium_term": {"price": "52.00", "horizon": "3-12 months", "thesis": "Mix shift continues."},
            "long_term": {"price": "60.00", "horizon": "12-36 months", "thesis": "Structural demand improves."},
        },
    }
    write_report_docx(output, payload=payload, language="zh")
    assert output.exists()
    assert output.stat().st_size > 0


def test_write_bilingual_report_docx_creates_single_docx_file(tmp_path: Path) -> None:
    output = tmp_path / "report.docx"
    zh_payload = {
        "company_name": "赛腾股份",
        "ticker": "603283.SH",
        "exchange": "SSE",
        "market": "CN",
        "model": "kimi-k2.5:cloud",
        "quick_take": "中文判断。",
        "verdict": "watchlist",
        "confidence": "high",
        "market_map": "中文市场图谱。",
        "business_summary": "中文业务概览。",
        "china_story": "中文角度。",
        "sentiment_simulation": "中文情绪。",
        "peer_comparison": "中文对比。",
        "committee_takeaways": "中文议会。",
        "scenario_outlook": "中文场景。",
        "debate_notes": "中文红队。",
        "valuation_view": "中文估值。",
        "bull_case": ["中文多头。"],
        "bear_case": ["中文空头。"],
        "catalysts": ["中文催化。"],
        "risks": ["中文风险。"],
        "next_questions": ["中文问题。"],
        "evidence": [{"title": "公告", "url": "https://example.com", "claim": "中文证据", "stance": "support"}],
        "target_prices": {"short_term": {"price": "45.00", "horizon": "1-3个月", "thesis": "中文依据"}},
    }
    en_payload = build_english_report_fallback(zh_payload)
    write_bilingual_report_docx(output, zh_payload=zh_payload, en_payload=en_payload)
    assert output.exists()
    assert output.stat().st_size > 0


def test_build_english_report_fallback_keeps_english_output_clean() -> None:
    payload = build_english_report_fallback(
        {
            "company_name": "赛腾股份",
            "ticker": "603283.SH",
            "quick_take": "需要继续验证客户结构。",
            "target_prices": {"short_term": {"price": "45.00", "horizon": "1-3个月", "thesis": "订单验证"}},
            "bull_case": ["订单质量仍待验证。"],
            "evidence": [{"title": "示例", "url": "https://example.com", "claim": "示例结论", "stance": "support"}],
        }
    )
    assert payload["company_name"] == "603283.SH"
    assert "Chinese report" in payload["quick_take"]
    assert "unavailable" not in payload["quick_take"].lower()
    assert payload["target_prices"]["short_term"]["horizon"] == "1-3 months"
    assert payload["bull_case"]


def test_looks_like_us_ticker_accepts_plain_us_symbols() -> None:
    assert looks_like_us_ticker("NPCE")
    assert looks_like_us_ticker("WLDS")
    assert not looks_like_us_ticker("603283.SH")
    assert not looks_like_us_ticker("300007")


def test_resolve_research_request_supports_ticker_and_market_only() -> None:
    request = resolve_research_request(identifier="603283.SH", ticker=None, market="", market_positional="CN")
    assert request == {"stock_name": "603283.SH", "ticker": "603283.SH", "market": "CN"}


def test_resolve_research_request_supports_plain_name_and_country() -> None:
    request = resolve_research_request(identifier="赛腾股份", ticker=None, market="", market_positional="中国")
    assert request == {"stock_name": "赛腾股份", "ticker": None, "market": "CN"}


def test_resolve_research_request_supports_plain_cn_code_and_country() -> None:
    request = resolve_research_request(identifier="603283", ticker=None, market="", market_positional="中国")
    assert request == {"stock_name": "603283.SH", "ticker": "603283.SH", "market": "CN"}


def test_resolve_research_request_corrects_common_us_company_typo() -> None:
    request = resolve_research_request(identifier="mircosoft", ticker=None, market="", market_positional="美国")
    assert request == {"stock_name": "Microsoft", "ticker": "MSFT", "market": "US"}


def test_build_interactive_command_args_builds_research_flow() -> None:
    answers = iter(["分析", "中国", "赛腾股份"])

    args = build_interactive_command_args(prompt_fn=lambda _: next(answers))

    assert args == ["research", "赛腾股份", "中国"]


def test_build_interactive_command_args_builds_screening_flow() -> None:
    answers = iter(["筛股", "美国", "脑机接口"])

    args = build_interactive_command_args(prompt_fn=lambda _: next(answers))

    assert args == ["screen", "脑机接口", "--market", "美国"]


def test_build_interactive_command_args_defaults_to_research_and_china_market() -> None:
    answers = iter(["", "", "603283"])

    args = build_interactive_command_args(prompt_fn=lambda _: next(answers))

    assert args == ["research", "603283", "中国"]


def test_main_without_args_routes_through_guided_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[object] = []
    monkeypatch.setattr(
        "stock_research_desk.stock_cli.build_interactive_command_args",
        lambda: ["screen", "脑机接口", "--market", "US"],
    )
    monkeypatch.setattr("stock_research_desk.stock_cli.dispatch_command", lambda args: captured.append(args))

    main([])

    assert captured
    assert getattr(captured[0], "command") == "screen"
    assert getattr(captured[0], "theme") == "脑机接口"
    assert getattr(captured[0], "market") == "US"


def test_resolve_research_request_preserves_legacy_name_and_ticker_flow() -> None:
    request = resolve_research_request(identifier="赛腾股份", ticker="603283.SH", market="CN", market_positional=None)
    assert request == {"stock_name": "赛腾股份", "ticker": "603283.SH", "market": "CN"}


def test_market_compatible_candidate_rejects_cn_names_for_us_screen() -> None:
    assert is_market_compatible_candidate(market="US", ticker="NPCE", company_name="NeuroPace", market_hint="US")
    assert not is_market_compatible_candidate(market="US", ticker="300007", company_name="汉威科技", market_hint="CN")


def test_build_seed_candidates_keeps_user_supplied_us_symbols() -> None:
    seeds = build_seed_candidates(seed_tickers=["NPCE", "WLDS"], theme="脑机接口", market="US")
    assert [item["ticker"] for item in seeds] == ["NPCE", "WLDS"]


def test_merge_seed_candidates_adds_missing_seed_and_keeps_orderable_scores() -> None:
    merged = merge_seed_candidates(
        candidates=[{"company_name": "NeuroOne", "ticker": "NMTC", "market": "US", "screen_score": 70, "confidence": "medium", "source_count": 2}],
        seeds=[{"company_name": "NPCE", "ticker": "NPCE", "market": "US", "screen_score": 88, "confidence": "medium", "source_count": 1}],
    )
    assert {item["ticker"] for item in merged} == {"NMTC", "NPCE"}
    assert merged[0]["ticker"] == "NPCE"


def test_combine_candidate_lists_prefers_stronger_fields_and_higher_scores() -> None:
    combined = combine_candidate_lists(
        [{"company_name": "NeuroPace", "ticker": "NPCE", "market": "US", "screen_score": 70, "source_count": 2, "confidence": "medium"}],
        [{"company_name": "NeuroPace", "ticker": "NPCE", "market": "US", "screen_score": 85, "source_count": 3, "confidence": "high", "why_now": "RNS traction"}],
        theme="脑机接口",
        market="US",
    )
    assert len(combined) == 1
    assert combined[0]["screen_score"] == 85
    assert combined[0]["confidence"] == "high"
    assert combined[0]["why_now"] == "RNS traction"


def test_normalize_evidence_drops_empty_rows() -> None:
    evidence = normalize_evidence(
        [
            {"title": "A", "url": "https://example.com", "claim": "x", "stance": "support"},
            {"title": "", "url": "", "claim": "", "stance": "neutral"},
        ]
    )
    assert len(evidence) == 1
    assert evidence[0]["title"] == "A"


def test_normalize_evidence_filters_low_quality_source_noise() -> None:
    evidence = normalize_evidence(
        [
            {
                "title": "财富号噪音",
                "url": "https://caifuhao.eastmoney.com/news/test",
                "claim": "标签添加class=foo 佛学 游戏 旅游 邮箱 导航",
                "stance": "neutral",
            },
            {
                "title": "赛腾股份2024年报|赛腾股份_新浪财经_新浪网",
                "url": "https://www.cninfo.com.cn/new/disclosure/detail",
                "claim": "赛腾股份半导体设备订单改善仍待客户结构验证。",
                "stance": "support",
            },
        ]
    )
    assert len(evidence) == 1
    assert evidence[0]["title"] == "赛腾股份2024年报"
    assert "标签添加class" not in evidence[0]["claim"]


def test_evidence_freshness_prefers_recent_announcements() -> None:
    assert extract_source_date("赛腾股份2026年3月15日订单公告") == "2026-03-15"
    recent = evidence_freshness_score(
        {"title": "赛腾股份2026年3月15日订单公告", "claim": "近期订单改善", "url": "https://www.cninfo.com.cn/test"},
        now=datetime.fromisoformat("2026-04-10T00:00:00+00:00"),
    )
    older = evidence_freshness_score(
        {"title": "赛腾股份2023年年度报告", "claim": "历史业务底蕴", "url": "https://www.cninfo.com.cn/old"},
        now=datetime.fromisoformat("2026-04-10T00:00:00+00:00"),
    )
    assert recent > older


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


def test_sanitize_source_text_drops_css_and_portal_category_noise() -> None:
    text = """
    标签添加class=foo bar baz
    佛学 游戏 旅游 邮箱 导航 汽车 教育 时尚 女性 星座 健康
    赛腾股份半导体设备订单改善仍待客户结构验证。
    """
    cleaned = sanitize_source_text(text)
    assert "标签添加class" not in cleaned
    assert "佛学" not in cleaned
    assert "客户结构验证" in cleaned


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


def test_clean_research_summary_drops_finance_portal_category_noise() -> None:
    summary = clean_research_summary(
        """
        理财| 银行 保险 黄金 外汇 债券 期货 股指期货
        切换到 电脑版
        报告要点：深耕消费电子设备，外延并购布局半导体及新能源板块。
        """
    )
    assert "理财" not in summary
    assert "电脑版" not in summary
    assert "半导体及新能源板块" in summary


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


def test_build_screening_fallback_candidates_extracts_us_exchange_tickers() -> None:
    candidates = build_screening_fallback_candidates(
        [
            {
                "title": "NeuroPace (Nasdaq: NPCE)",
                "claim": "NeuroPace is a commercial-stage neurotech company.",
                "quality": "84",
            }
        ],
        theme="脑机接口",
        market="US",
    )
    assert candidates[0]["ticker"] == "NPCE"
    assert "NeuroPace" in candidates[0]["company_name"]


def test_derive_company_identity_recovers_company_name_and_otc_ticker_from_press_release() -> None:
    company_name, ticker = derive_company_identity(
        market="US",
        candidate={"company_name": "ONWARD Medical Builds Commercial Momentum for the ARC", "ticker": "SKIP"},
        evidence=[
            {
                "title": "ONWARD Medical Builds Commercial Momentum for the ARC-EX System and Reinforces its Brain-Computer Interface Leadership in Q1 2025 | Nasdaq",
                "claim": "Eindhoven, the Netherlands — ONWARD Medical N.V. (Euronext: ONWD and US OTCQX: ONWRY), the leading neurotechnology company...",
                "excerpt": "",
            }
        ],
        note="",
    )
    assert company_name == "ONWARD Medical"
    assert ticker == "ONWRY"


def test_clean_company_name_style_noise_is_removed_via_identity_resolution() -> None:
    company_name, ticker = derive_company_identity(
        market="US",
        candidate={"company_name": "Nexalin Technology Stock Price Today NXL", "ticker": "NXL"},
        evidence=[],
        note="",
    )
    assert company_name == "Nexalin Technology"
    assert ticker == "NXL"


def test_derive_company_identity_does_not_collapse_to_suffix_only_entity() -> None:
    company_name, ticker = derive_company_identity(
        market="US",
        candidate={"company_name": "Nexalin Technology Stock Price Today NXL", "ticker": "NXL"},
        evidence=[
            {
                "title": "Nexalin Technology, Inc. (NASDAQ: NXL) advances neurostimulation strategy",
                "claim": "Nexalin Technology, Inc. (NASDAQ: NXL) is a publicly traded healthcare company.",
                "excerpt": "",
            }
        ],
        note="",
    )
    assert company_name == "Nexalin Technology"
    assert ticker == "NXL"


def test_sector_profile_for_bci_includes_anchor_names_and_query_axes() -> None:
    profile = sector_profile_for("脑机接口", "US")
    assert "brain-computer interface" in profile["keywords"]
    assert any("NeuroPace" in item for item in profile["listed_anchor_names"])
    assert any("public neurotechnology companies" in item for item in profile["query_axes"])


def test_sector_profile_for_humanoid_robotics_has_specialized_query_axes() -> None:
    profile = sector_profile_for("人形机器人", "US")
    assert profile["sector"] == "humanoid robotics"
    assert any("humanoid robotics" in item for item in profile["query_axes"])
    assert any("pure-play humanoid" in item for item in profile["focus_questions"])


def test_default_sector_query_axes_support_unknown_sparse_themes() -> None:
    axes = default_sector_query_axes("卫星互联网", "US")
    assert any("US-listed 卫星互联网 companies" in item for item in axes)
    profile = sector_profile_for("卫星互联网", "US")
    assert profile["keywords"] == ["卫星互联网"]
    assert len(profile["query_axes"]) >= 5


def test_normalize_screen_candidates_filters_non_us_names_when_screening_us() -> None:
    normalized = normalize_screen_candidates(
        [
            {"company_name": "NeuroPace", "ticker": "NPCE", "market": "US", "screen_score": 82},
            {"company_name": "汉威科技", "ticker": "300007", "market": "CN", "screen_score": 95},
        ],
        theme="脑机接口",
        market="US",
    )
    assert len(normalized) == 1
    assert normalized[0]["ticker"] == "NPCE"


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
    assert "recent_developments" in payload
    assert "report_markdown" in payload


def test_normalize_report_payload_prefers_resolved_company_name_over_ticker_label() -> None:
    payload = normalize_report_payload(
        {"company_name": "603283.SH", "ticker": "603283.SH", "evidence": []},
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        model="glm-5:cloud",
    )
    assert payload["company_name"] == "赛腾股份"


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
        recent_developments="最近90天公告与订单线索仍需继续跟踪。",
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
    assert "## 最新实效信息与波动线索" in markdown
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


def test_normalize_cloud_model_name_maps_user_shorthand() -> None:
    assert normalize_cloud_model_name("qwen3.5:397b") == "qwen3.5:cloud"
    assert normalize_cloud_model_name("gemini-3-flash-preview") == "gemini-3-flash-preview:cloud"
    assert normalize_cloud_model_name("glm-5.1") == "glm-5.1:cloud"


def test_build_cloud_model_chain_uses_default_glm_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_RESEARCH_DESK_MODEL_FALLBACKS", raising=False)
    assert build_cloud_model_chain("glm-5.1:cloud") == (
        "glm-5.1:cloud",
        "kimi-k2.5:cloud",
        "qwen3.5:cloud",
    )


def test_build_cloud_model_chain_keeps_primary_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_RESEARCH_DESK_MODEL_FALLBACKS", "qwen3.5:397b, glm-5.1")
    assert build_cloud_model_chain("kimi-k2.5:cloud") == (
        "kimi-k2.5:cloud",
        "qwen3.5:cloud",
        "glm-5.1:cloud",
    )


def test_chat_with_guard_falls_back_to_next_cloud_model() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.models: list[str] = []

        def chat(self, **kwargs: object) -> object:
            model = str(kwargs["model"])
            self.models.append(model)
            if model == "kimi-k2.5:cloud":
                raise RuntimeError("primary unavailable")
            return object()

    client = FakeClient()
    result = chat_with_guard(
        client,  # type: ignore[arg-type]
        timeout_seconds=1,
        model_chain=("kimi-k2.5:cloud", "qwen3.5:cloud"),
        model="kimi-k2.5:cloud",
        messages=[],
        think="high",
    )
    assert result is not None
    assert client.models == ["kimi-k2.5:cloud", "qwen3.5:cloud"]


def test_chat_with_guard_aborts_after_all_cloud_models_fail() -> None:
    class FakeClient:
        def chat(self, **kwargs: object) -> object:
            raise RuntimeError(f"{kwargs['model']} unavailable")

    with pytest.raises(RuntimeError, match="model chain failed"):
        chat_with_guard(
            FakeClient(),  # type: ignore[arg-type]
            timeout_seconds=1,
            model_chain=("kimi-k2.5:cloud", "qwen3.5:cloud"),
            model="kimi-k2.5:cloud",
            messages=[],
            think="high",
        )


def test_default_workspace_home_prefers_desktop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("STOCK_RESEARCH_DESK_HOME", raising=False)
    monkeypatch.setattr("stock_research_desk.stock_cli.Path.home", classmethod(lambda cls: tmp_path))
    assert default_workspace_home() == (tmp_path / ".stock-research-desk").resolve()


def test_default_desktop_delivery_dir_points_to_desktop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("stock_research_desk.stock_cli.Path.home", classmethod(lambda cls: tmp_path))
    assert default_desktop_delivery_dir() == (tmp_path / "Desktop").resolve()


def test_resolve_workspace_paths_builds_desktop_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STOCK_RESEARCH_DESK_HOME", str(tmp_path / "desk-home"))
    monkeypatch.setattr("stock_research_desk.stock_cli.Path.home", classmethod(lambda cls: tmp_path))
    paths = resolve_workspace_paths("reports")
    assert paths.reports_dir == (tmp_path / "Desktop").resolve()
    assert paths.memory_dir == (tmp_path / "desk-home" / "memory_palace").resolve()
    assert paths.screens_dir == (tmp_path / "Desktop").resolve()
    assert paths.watchlist_path == (tmp_path / "desk-home" / "watchlist.json").resolve()


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
    assert "最近90天" in market_prompt
    assert "web_fetch" in company_prompt
    assert "Warren Buffett" in company_prompt
    assert "最新公告" in company_prompt
    assert "成长基金视角" in sentiment_prompt
    assert "Cathie Wood" in sentiment_prompt
    assert "未来1-3个月" in sentiment_prompt


def test_screening_council_prompts_are_multi_stage() -> None:
    bull_prompt = build_screening_council_bull_prompt()
    red_prompt = build_screening_council_red_prompt()
    reconsider_prompt = build_screening_council_reconsider_prompt()

    assert "支持派" in bull_prompt
    assert "红队" in red_prompt
    assert "复议" in reconsider_prompt


def test_search_fallback_only_runs_on_primary_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSearchResponse:
        def model_dump(self) -> dict[str, object]:
            return {"results": [{"title": "Primary", "url": "https://example.com", "content": "ok"}]}

    class FakeClient:
        def web_search(self, **kwargs: object) -> FakeSearchResponse:
            return FakeSearchResponse()

    def fake_fallback(**kwargs: object) -> dict[str, object]:
        return {"results": [{"title": "Fallback", "url": "https://fallback.example", "content": "fallback"}]}

    monkeypatch.setattr("stock_research_desk.stock_cli.fallback_search_with_cross_validated", fake_fallback)
    result = perform_search_with_fallback(client=FakeClient(), query="脑机接口 美股", max_results=5, market="US")
    assert result["results"][0]["title"] == "Primary"


def test_search_fallback_activates_on_primary_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def web_search(self, **kwargs: object) -> object:
            raise RuntimeError("primary failed")

    def fake_fallback(**kwargs: object) -> dict[str, object]:
        return {"results": [{"title": "Fallback", "url": "https://fallback.example", "content": "fallback"}]}

    monkeypatch.setattr("stock_research_desk.stock_cli.fallback_search_with_cross_validated", fake_fallback)
    result = perform_search_with_fallback(client=FakeClient(), query="脑机接口 美股", max_results=5, market="US")
    assert result["results"][0]["title"] == "Fallback"
    assert "primary_error" in result


def test_fetch_fallback_activates_on_primary_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFetchResponse:
        def model_dump(self) -> dict[str, object]:
            return {"url": "https://example.com", "error": "tool failed"}

    class FakeClient:
        def web_fetch(self, **kwargs: object) -> FakeFetchResponse:
            return FakeFetchResponse()

    def fake_fallback(**kwargs: object) -> dict[str, object]:
        return {"url": "https://example.com", "title": "Fallback Page", "content": "fallback", "excerpt": "fallback"}

    monkeypatch.setattr("stock_research_desk.stock_cli.fallback_fetch_with_cross_validated", fake_fallback)
    result = perform_fetch_with_fallback(client=FakeClient(), url="https://example.com")
    assert result["title"] == "Fallback Page"
    assert result["primary_error"] == "tool failed"


def test_second_screen_prompt_requires_committee_notes_and_rounds() -> None:
    prompt = build_second_screen_prompt(
        theme="脑机接口",
        market="US",
        desired_count=3,
        candidates=[{"company_name": "Neuralink Proxy", "ticker": "ABCD", "market": "US"}],
        bull_round="支持派认为产业催化剂存在。",
        red_round="红队质疑商业化时点。",
        reconsideration_round="复议后只保留少数高质量名字。",
    )
    assert "committee_notes" in prompt
    assert "bull_round" in prompt
    assert "red_round" in prompt
    assert "reconsideration_round" in prompt


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
        macro_policy_strategist=FakeResult("macro_policy_strategist", "宏观结论"),
        company_analyst=FakeResult("company_analyst", "公司结论"),
        catalyst_event_tracker=FakeResult("catalyst_event_tracker", "催化结论"),
        sentiment_simulator=FakeResult("sentiment_simulator", "情绪结论"),
        technical_flow_analyst=FakeResult("technical_flow_analyst", "技术面结论"),
        comparison_analyst=FakeResult("comparison_analyst", "对比结论"),
        quant_factor_analyst=FakeResult("quant_factor_analyst", "因子结论"),
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
    assert "technical_view" in prompt
    assert "factor_exposure" in prompt
    assert "catalyst_calendar" in prompt
    assert "macro_context" in prompt
    assert "flow_signal" in prompt


def test_normalize_verdict_maps_freeform_labels() -> None:
    assert normalize_verdict("谨慎乐观") == "bullish"
    assert normalize_verdict("回避") == "bearish"
    assert normalize_verdict("继续观察") == "watchlist"
    assert normalize_verdict("neutral") == "neutral"
    assert normalize_verdict("买入") == "bullish"
    assert normalize_verdict("卖出") == "bearish"


def test_normalize_confidence_maps_numeric_and_chinese_labels() -> None:
    assert normalize_confidence("4") == "high"
    assert normalize_confidence("中等") == "medium"
    assert normalize_confidence("低") == "low"


def test_normalize_ticker_adds_china_suffix_from_exchange() -> None:
    assert normalize_ticker("603283", "SSE", "CN") == "603283.SH"


def test_normalize_market_hint_accepts_country_names() -> None:
    assert normalize_market_hint("中国") == "CN"
    assert normalize_market_hint("美股") == "US"
    assert normalize_market_hint("香港") == "HK"


def test_normalize_ticker_adds_china_suffix_without_exchange() -> None:
    assert normalize_ticker("603283", "", "CN") == "603283.SH"
    assert normalize_ticker("300750", "", "CN") == "300750.SZ"


def test_parse_interval_hours_supports_hours_days_and_weeks() -> None:
    assert parse_interval_hours("24h") == 24
    assert parse_interval_hours("3d") == 72
    assert parse_interval_hours("1w") == 168


def test_normalize_screen_candidates_dedupes_and_sorts() -> None:
    payload = normalize_screen_candidates(
        [
            {"company_name": "赛腾股份", "ticker": "603283", "screen_score": 77, "confidence": "high", "source_count": 3},
            {"company_name": "赛腾股份", "ticker": "603283.SH", "screen_score": 60, "confidence": "low", "source_count": 1},
            {"company_name": "中科飞测", "ticker": "688361", "screen_score": 88, "confidence": "medium", "source_count": 2},
        ],
        theme="先进制造",
        market="CN",
    )
    assert len(payload) == 2
    assert payload[0]["ticker"] == "688361.SH"
    assert payload[1]["ticker"] == "603283.SH"


def test_build_screening_fallback_candidates_extracts_stock_names_from_evidence() -> None:
    candidates = build_screening_fallback_candidates(
        [
            {
                "title": "赛腾股份(603283)年报摘要",
                "url": "https://www.cninfo.com.cn/test",
                "claim": "赛腾股份在半导体设备与消费电子自动化方向具备继续研究价值。",
                "quality": "96",
                "stance": "neutral",
            }
        ],
        theme="中国机器人",
        market="CN",
    )
    assert candidates[0]["company_name"] == "赛腾股份"
    assert candidates[0]["ticker"] == "603283.SH"


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


def test_watchlist_add_and_remove_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STOCK_RESEARCH_DESK_HOME", str(tmp_path / "desk-home"))
    paths = resolve_workspace_paths("reports")
    entry = add_watchlist_entry(
        paths=paths,
        stock_name="赛腾股份",
        ticker="603283.SH",
        market="CN",
        angle="中国故事",
        interval_spec="7d",
    )
    loaded = load_watchlist(paths)
    assert entry["identifier"] == "603283-sh"
    assert loaded[0]["ticker"] == "603283.SH"
    removed = remove_watchlist_entry(paths, "603283.SH")
    assert removed == "603283.SH"
    assert load_watchlist(paths) == []


def test_resolve_workspace_paths_enables_single_document_delivery_on_desktop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STOCK_RESEARCH_DESK_HOME", str(tmp_path / "desk-home"))
    monkeypatch.setattr("stock_research_desk.stock_cli.Path.home", classmethod(lambda cls: tmp_path))
    paths = resolve_workspace_paths("reports")
    assert paths.single_document_delivery is True
    assert paths.artifacts_dir.exists()
    report_paths = build_report_document_paths(reports_dir=paths.reports_dir, timestamp="20260410-000000", slug="603283-sh", single_document=paths.single_document_delivery)
    digest_paths = build_watchlist_digest_document_paths(digests_dir=paths.digests_dir, timestamp="20260410-000000", single_document=paths.single_document_delivery)
    assert report_paths["primary"] == report_paths["zh"] == report_paths["en"]
    assert digest_paths["primary"] == digest_paths["zh"] == digest_paths["en"]


def test_fetch_company_name_from_ticker_reads_cn_name(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"data":{"f58":"\xe8\xb5\x9b\xe8\x85\xbe\xe8\x82\xa1\xe4\xbb\xbd"}}'

    monkeypatch.setattr("stock_research_desk.stock_cli.urlopen", lambda *args, **kwargs: FakeResponse())
    assert fetch_company_name_from_ticker("603283.SH", "CN") == "赛腾股份"


def test_resolve_stock_name_prefers_company_lookup_for_ticker_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stock_research_desk.stock_cli.fetch_company_name_from_ticker", lambda ticker, market: "赛腾股份")
    assert resolve_stock_name(stock_name="603283.SH", ticker="603283.SH", market="CN") == "赛腾股份"


def test_load_local_env_file_populates_missing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("STOCK_RESEARCH_DESK_HOME", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OLLAMA_API_KEY=test-key\nSTOCK_RESEARCH_DESK_HOME=~/.stock-research-desk\n")
    load_local_env_file(env_path)
    assert os.environ["OLLAMA_API_KEY"] == "test-key"
    assert os.environ["STOCK_RESEARCH_DESK_HOME"].endswith(".stock-research-desk")


def test_load_local_env_file_does_not_override_existing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "already-set")
    env_path = tmp_path / ".env"
    env_path.write_text("OLLAMA_API_KEY=test-key\n")
    load_local_env_file(env_path)
    assert os.environ["OLLAMA_API_KEY"] == "already-set"


def test_run_due_watchlist_updates_next_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STOCK_RESEARCH_DESK_HOME", str(tmp_path / "desk-home"))
    paths = resolve_workspace_paths("reports")
    save_watchlist(
        paths,
        [
            {
                "identifier": "603283-sh",
                "stock_name": "赛腾股份",
                "ticker": "603283.SH",
                "market": "CN",
                "angle": "中国故事",
                "interval_spec": "1d",
                "interval_hours": 24,
                "next_run_at": "2026-04-01T00:00:00+00:00",
                "last_run_at": None,
                "last_report_path": "",
            }
        ],
    )

    def fake_run_stock_research(**_: object) -> dict[str, object]:
        return {
            "zh_docx_path": "/tmp/report-zh.docx",
            "en_docx_path": "/tmp/report-en.docx",
            "primary_document_path": "/tmp/report-zh.docx",
            "json_path": "/tmp/report.json",
            "memory_path": "/tmp/memory.json",
            "payload": {"verdict": "watchlist"},
        }

    monkeypatch.setattr("stock_research_desk.stock_cli.run_stock_research", fake_run_stock_research)

    class FakeConfig:
        pass

    result = run_due_watchlist(paths=paths, config=FakeConfig(), limit=5, verbose=False)
    updated = load_watchlist(paths)
    assert result["processed"] == 1
    assert updated[0]["last_report_path"] == "/tmp/report-zh.docx"
    assert updated[0]["next_run_at"] != "2026-04-01T00:00:00+00:00"
    assert result["digest_path"] == ""
    assert result["zh_digest_path"] == ""
    assert result["en_digest_path"] == ""


def test_render_watchlist_digest_markdown_includes_verdict_and_path() -> None:
    markdown = render_watchlist_digest_markdown(
        [
            {
                "identifier": "603283-sh",
                "primary_document_path": "/tmp/report-zh.docx",
                "verdict": "watchlist",
                "quick_take": "仍需继续验证订单质量。",
            }
        ]
    )
    assert "Watchlist" in markdown
    assert "603283-sh" in markdown
    assert "/tmp/report-zh.docx" in markdown


def test_parse_email_command_supports_research_screen_and_watchlist() -> None:
    research = parse_email_command(subject="research: 赛腾股份 |  | 中国", body="")
    screen = parse_email_command(subject="screen: 中国机器人 | 3 | 中国", body="")
    watchlist = parse_email_command(subject="watchlist add: 赛腾股份 |  | 7d | 中国", body="")
    assert research is not None and research["kind"] == "research"
    assert research["ticker"] == ""
    assert research["market"] == "CN"
    assert screen is not None and screen["kind"] == "screen"
    assert screen["count"] == 3
    assert screen["market"] == "CN"
    assert watchlist is not None and watchlist["kind"] == "watchlist_add"
    assert watchlist["interval"] == "7d"
    assert watchlist["market"] == "CN"


def test_parse_email_command_supports_watchlist_short_commands() -> None:
    assert parse_email_command(subject="watchlist list", body="") == {"kind": "watchlist_list"}
    assert parse_email_command(subject="watchlist run-due", body="") == {"kind": "watchlist_run_due"}


def test_render_email_research_reply_includes_bull_risk_and_targets() -> None:
    body = render_email_research_reply(
        {
            "company_name": "赛腾股份",
            "verdict": "watchlist",
            "confidence": "medium",
            "quick_take": "订单质量还需要更多验证。",
            "bull_case": ["国产替代主线仍在。"],
            "risks": ["客户集中度偏高。"],
            "target_prices": {
                "short_term": {"price": "45.5", "horizon": "1-3个月", "thesis": "订单验证"},
                "medium_term": {"price": "52", "horizon": "3-12个月", "thesis": "估值锚修复"},
                "long_term": {"price": "60", "horizon": "12-36个月", "thesis": "质量重估"},
            },
        },
        "/tmp/report-zh.docx",
    )
    assert "Single-Name Desk Note" in body
    assert "Top bull points" in body
    assert "Key risks" in body
    assert "Short: 45.5" in body


def test_render_email_screen_reply_includes_why_now_and_counts() -> None:
    body = render_email_screen_reply(
        theme="中国机器人",
        payload={
            "initial_candidates": [{"company_name": "A"}] * 7,
            "stage_one_candidates": [{"company_name": "A"}] * 4,
            "finalists": [
                {
                    "company_name": "赛腾股份",
                    "ticker": "603283.SH",
                    "screen_score": 82,
                    "stage_two_note": "订单和产业趋势的交集更清晰。",
                    "payload": {
                        "verdict": "watchlist",
                        "quick_take": "值得继续研究。",
                        "target_prices": {"short_term": {"price": "45", "horizon": "1-3个月"}},
                    },
                }
            ],
        },
        document_path="/tmp/screen-zh.docx",
    )
    assert "Screening Brief" in body
    assert "Initial candidates: 7" in body
    assert "Second-screen pool: 4" in body
    assert "why_now: 订单和产业趋势的交集更清晰。" in body
    assert "targets: ST 45 (1-3个月)" in body


def test_format_target_price_snapshot_collapses_three_horizons() -> None:
    snapshot = format_target_price_snapshot(
        {
            "short_term": {"price": "45", "horizon": "1-3个月"},
            "medium_term": {"price": "52", "horizon": "3-12个月"},
            "long_term": {"price": "60", "horizon": "12-36个月"},
        }
    )
    assert "ST 45 (1-3个月)" in snapshot
    assert "MT 52 (3-12个月)" in snapshot
    assert "LT 60 (12-36个月)" in snapshot


def test_desk_briefing_mode_switches_on_monday() -> None:
    assert desk_briefing_mode(datetime.fromisoformat("2026-04-13T08:00:00+00:00")) == "weekly"
    assert desk_briefing_mode(datetime.fromisoformat("2026-04-15T08:00:00+00:00")) == "morning"


def test_render_email_watchlist_digest_reply_uses_briefing_format() -> None:
    body = render_email_watchlist_digest_reply(
        {
            "processed": 2,
            "digest_path": "",
            "artifacts": [
                {
                    "identifier": "603283-sh",
                    "verdict": "watchlist",
                    "quick_take": "半导体弹性仍待验证。",
                    "target_snapshot": "ST 45 (1-3个月)",
                }
            ],
        }
    )
    assert "Watchlist" in body
    assert "Desk highlights" in body
    assert "Attached digest" not in body
    assert "target_snapshot" not in body
    assert "ST 45 (1-3个月)" in body


def test_render_email_watchlist_roster_reply_lists_priority_queue() -> None:
    body = render_email_watchlist_roster_reply(
        [
            {
                "stock_name": "赛腾股份",
                "ticker": "603283.SH",
                "interval_spec": "7d",
                "next_run_at": "2026-04-16T08:00:00+00:00",
                "last_run_at": None,
            }
        ]
    )
    assert "Coverage Roster" in body
    assert "Priority queue" in body
    assert "603283.SH" in body


def test_unique_attachment_paths_deduplicates_single_document_delivery() -> None:
    attachments = unique_attachment_paths("/tmp/report.docx", "/tmp/report.docx", "", None, "/tmp/other.docx")
    assert attachments == ["/tmp/report.docx", "/tmp/other.docx"]


def test_render_watchlist_digest_markdown_includes_target_snapshot() -> None:
    markdown = render_watchlist_digest_markdown(
        [
            {
                "identifier": "603283-sh",
                "primary_document_path": "/tmp/report-zh.docx",
                "verdict": "watchlist",
                "quick_take": "半导体弹性仍待验证。",
                "target_snapshot": "ST 45 (1-3个月)",
            }
        ]
    )
    assert "Desk Summary" in markdown
    assert "Target snapshot" in markdown


def test_render_screening_markdown_includes_summary_rank_and_rejects() -> None:
    markdown = render_screening_markdown(
        theme="中国机器人",
        market="CN",
        stage_one_candidates=[
            {"company_name": "赛腾股份", "ticker": "603283.SH", "screen_score": 82, "rationale": "先进制造逻辑更强。"},
            {"company_name": "中科飞测", "ticker": "688361.SH", "screen_score": 75, "rationale": "更偏设备纯度。"},
        ],
        finalists=[
            {
                "company_name": "赛腾股份",
                "ticker": "603283.SH",
                "screen_score": 82,
                "stage_two_note": "why now 更明确。",
                "primary_document_path": "/tmp/report-zh.docx",
                "why_not_now": "仍需验证客户结构改善。",
                "vertical_summary": "业务与主题契合度更高。",
                "horizontal_summary": "相对同类更适合优先深研。",
                "payload": {
                    "verdict": "watchlist",
                    "confidence": "medium",
                    "quick_take": "值得继续深挖。",
                    "bull_case": ["国产替代主线仍在。"],
                    "bear_case": ["客户集中度仍高。"],
                    "target_prices": {"short_term": {"price": "45", "horizon": "1-3个月"}},
                },
            }
        ],
    )
    assert "## 推荐摘要" in markdown
    assert "Recommendation rank" in markdown
    assert "## 本轮未晋级名单" in markdown
    assert "Vertical summary" in markdown
    assert "Why not now" in markdown


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


def test_extract_target_prices_from_text_reads_usd_ranges() -> None:
    payload = extract_target_prices_from_text(
        """
        - 短期（3-6个月）：$395-425，依据：cloud spend and AI sentiment stabilization.
        - 中期（12-18个月）：$520-580，依据：Azure AI monetization and margin recovery.
        - 长期（36个月）：$650-720，依据：durable platform compounding.
        """
    )
    assert payload["short_term"]["price"] == "410"
    assert payload["medium_term"]["price"] == "550"
    assert payload["long_term"]["price"] == "685"


def test_extract_target_prices_from_text_prioritizes_heading_targets() -> None:
    payload = extract_target_prices_from_text(
        """
        ### 短期目标价：$425 - $465 | 时间轴：3-6个月
        ### 中期目标价：$540 - $610 | 时间轴：12-18个月
        ### 长期目标价：$680 - $820 | 时间轴：24-36个月
        - 监控P/FCF倍数：当前~28x（假设FCF $13/share）若无法压缩至<20x，则长期目标$800不可达
        """
    )
    assert payload["short_term"]["price"] == "445"
    assert payload["medium_term"]["price"] == "575"
    assert payload["long_term"]["price"] == "750"


def test_derive_target_prices_from_context_reads_usd_current_price() -> None:
    payload = derive_target_prices_from_context("当前价格基准：$372.29", verdict="watchlist")
    assert payload["medium_term"]["price"] == "416.96"


def test_normalize_screen_candidates_keeps_diligence_fields() -> None:
    candidates = normalize_screen_candidates(
        [
            {
                "company_name": "赛腾股份",
                "ticker": "603283.SH",
                "screen_score": 80,
                "why_now": "订单和主题共振更明确。",
                "why_not_now": "客户集中度仍高。",
                "vertical_summary": "业务与主题契合度更高。",
                "horizontal_summary": "横向更值得继续优先研究。",
            }
        ],
        theme="中国机器人",
        market="CN",
    )
    assert candidates[0]["why_now"] == "订单和主题共振更明确。"
    assert candidates[0]["why_not_now"] == "客户集中度仍高。"
    assert candidates[0]["vertical_summary"] == "业务与主题契合度更高。"


def test_merge_screen_candidates_restores_stage_one_dossier_fields() -> None:
    merged = merge_screen_candidates(
        [
            {
                "company_name": "赛腾股份",
                "ticker": "603283.SH",
                "screen_score": 88,
                "rationale": "why now 更明确。",
            }
        ],
        references=[
            {
                "company_name": "赛腾股份",
                "ticker": "603283.SH",
                "screen_score": 81,
                "vertical_summary": "业务与主题契合。",
                "horizontal_summary": "横向更值得继续研究。",
                "why_not_now": "客户集中度仍高。",
            }
        ],
    )
    assert merged[0]["vertical_summary"] == "业务与主题契合。"
    assert merged[0]["horizontal_summary"] == "横向更值得继续研究。"
    assert merged[0]["why_not_now"] == "客户集中度仍高。"


def test_merge_screen_candidates_prefers_cleaner_legal_entity_name() -> None:
    merged = merge_screen_candidates(
        [
            {
                "company_name": "Nexalin Technology Stock Price Today NXL",
                "ticker": "NXL",
                "screen_score": 88,
            }
        ],
        references=[
            {
                "company_name": "Nexalin Technology, Inc.",
                "ticker": "NXL",
                "screen_score": 80,
                "vertical_summary": "real company",
            }
        ],
    )
    assert merged[0]["company_name"] == "Nexalin Technology"
    assert merged[0]["vertical_summary"] == "real company"


def test_source_quality_score_prefers_official_domains() -> None:
    assert source_quality_score("https://www.cninfo.com.cn/test") > source_quality_score("https://finance.sina.com.cn/test")


def test_source_quality_score_prefers_exact_subdomain_over_root_domain() -> None:
    assert source_quality_score("https://caifuhao.eastmoney.com/news/test") < source_quality_score("https://www.eastmoney.com/test")
    assert source_quality_score("https://ai.xueqiu.com/test") < 36


def test_derive_target_prices_from_context_builds_numeric_fallbacks() -> None:
    payload = derive_target_prices_from_context(
        "当前价格基准：47.64元，估值仍待验证。",
        verdict="watchlist",
    )
    assert payload["short_term"]["price"]
    assert payload["medium_term"]["price"]
    assert payload["long_term"]["price"]


def test_normalize_target_prices_rejects_stock_code_like_prices() -> None:
    payload = normalize_target_prices(
        {"long_term": {"price": "302654", "horizon": "2025年", "thesis": "研报标题噪音"}},
        {"long_term": {"price": "58.76", "horizon": "12-36个月", "thesis": "业务质量抬升"}},
    )
    assert payload["long_term"]["price"] == "58.76"
    assert payload["long_term"]["horizon"] == "12-36个月"
    assert payload["long_term"]["thesis"] == "业务质量抬升"
