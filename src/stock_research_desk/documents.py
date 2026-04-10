from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def english_safe_text(text: str, fallback: str) -> str:
    candidate = str(text or "").strip()
    if not candidate:
        return fallback
    if contains_cjk(candidate):
        return fallback
    return candidate


def build_english_report_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    ticker = str(payload.get("ticker") or "UNKNOWN").strip() or "UNKNOWN"
    company_name = str(payload.get("company_name") or "").strip()
    safe_company_name = ticker if contains_cjk(company_name) else (company_name or ticker)
    return {
        "company_name": safe_company_name,
        "ticker": ticker,
        "exchange": english_safe_text(str(payload.get("exchange") or ""), "n/a"),
        "market": english_safe_text(str(payload.get("market") or ""), "n/a"),
        "quick_take": english_safe_text(str(payload.get("quick_take") or ""), "Automatic English translation was unavailable in this run. Use the Chinese report as the primary source of truth."),
        "verdict": english_safe_text(str(payload.get("verdict") or ""), "watchlist"),
        "confidence": english_safe_text(str(payload.get("confidence") or ""), "medium"),
        "market_map": english_safe_text(str(payload.get("market_map") or ""), "English translation was unavailable for the market map in this run."),
        "business_summary": english_safe_text(str(payload.get("business_summary") or ""), "English translation was unavailable for the business summary in this run."),
        "china_story": english_safe_text(str(payload.get("china_story") or ""), "English translation was unavailable for the angle-specific narrative in this run."),
        "sentiment_simulation": english_safe_text(str(payload.get("sentiment_simulation") or ""), "English translation was unavailable for the sentiment simulation in this run."),
        "peer_comparison": english_safe_text(str(payload.get("peer_comparison") or ""), "English translation was unavailable for the peer comparison in this run."),
        "committee_takeaways": english_safe_text(str(payload.get("committee_takeaways") or ""), "English translation was unavailable for the investor council notes in this run."),
        "scenario_outlook": english_safe_text(str(payload.get("scenario_outlook") or ""), "English translation was unavailable for the scenario outlook in this run."),
        "debate_notes": english_safe_text(str(payload.get("debate_notes") or ""), "English translation was unavailable for the dissent note in this run."),
        "valuation_view": english_safe_text(str(payload.get("valuation_view") or ""), "English translation was unavailable for the valuation view in this run."),
        "bull_case": _english_safe_list(payload.get("bull_case"), "No translated bull points were available in this run."),
        "bear_case": _english_safe_list(payload.get("bear_case"), "No translated bear points were available in this run."),
        "catalysts": _english_safe_list(payload.get("catalysts"), "No translated catalysts were available in this run."),
        "risks": _english_safe_list(payload.get("risks"), "No translated risks were available in this run."),
        "next_questions": _english_safe_list(payload.get("next_questions"), "No translated follow-up questions were available in this run."),
        "evidence": _english_safe_evidence(payload.get("evidence")),
        "target_prices": payload.get("target_prices") or {},
    }


def build_screening_doc_payload(*, theme: str, market: str, stage_one_candidates: list[dict[str, Any]], finalists: list[dict[str, Any]]) -> dict[str, Any]:
    rejected = [
        item
        for item in stage_one_candidates
        if _candidate_identity(item) not in {_candidate_identity(finalist) for finalist in finalists}
    ]
    return {
        "theme": theme,
        "market": market,
        "generated_at": "",
        "stage_one_candidates": [
            {
                "company_name": str(item.get("company_name") or "").strip(),
                "ticker": str(item.get("ticker") or "").strip(),
                "screen_score": item.get("screen_score"),
                "why_now": str(item.get("why_now") or item.get("rationale") or "").strip(),
                "vertical_summary": str(item.get("vertical_summary") or "").strip(),
                "horizontal_summary": str(item.get("horizontal_summary") or "").strip(),
                "why_not_now": str(item.get("why_not_now") or "").strip(),
            }
            for item in stage_one_candidates
        ],
        "finalists": [
            {
                "company_name": str(item.get("company_name") or "").strip(),
                "ticker": str(item.get("ticker") or "").strip(),
                "screen_score": item.get("screen_score"),
                "recommendation_rank": str(item.get("recommendation_rank") or "").strip(),
                "research_verdict": str((item.get("payload") or {}).get("verdict") or "").strip(),
                "confidence": str((item.get("payload") or {}).get("confidence") or "").strip(),
                "why_now": str(item.get("stage_two_note") or item.get("rationale") or "").strip(),
                "why_not_now": str(item.get("why_not_now") or "").strip(),
                "quick_take": str((item.get("payload") or {}).get("quick_take") or "").strip(),
                "vertical_summary": str(item.get("vertical_summary") or "").strip(),
                "horizontal_summary": str(item.get("horizontal_summary") or "").strip(),
                "bull_bear_focus": str(summarize_bull_bear_for_doc(item.get("payload") or {})).strip(),
                "short_term_target": _target_snapshot((item.get("payload") or {}).get("target_prices") or {}, "short_term"),
                "document_path": str(item.get("primary_document_path") or item.get("zh_docx_path") or item.get("markdown_path") or "").strip(),
            }
            for item in finalists
        ],
        "rejected": [
            {
                "label": str(item.get("ticker") or item.get("company_name") or "").strip(),
                "reason": str(item.get("exclusion_reason") or item.get("why_not_now") or item.get("rationale") or "research upside was weaker").strip(),
            }
            for item in rejected[:8]
        ],
    }


def build_english_screening_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "theme": english_safe_text(str(payload.get("theme") or ""), "theme"),
        "market": english_safe_text(str(payload.get("market") or ""), "market"),
        "generated_at": str(payload.get("generated_at") or ""),
        "stage_one_candidates": [
            {
                "company_name": _safe_company_label(item),
                "ticker": str(item.get("ticker") or "").strip(),
                "screen_score": item.get("screen_score"),
                "why_now": english_safe_text(str(item.get("why_now") or ""), "Why-now translation was unavailable for this candidate."),
                "vertical_summary": english_safe_text(str(item.get("vertical_summary") or ""), "Vertical diligence translation was unavailable."),
                "horizontal_summary": english_safe_text(str(item.get("horizontal_summary") or ""), "Horizontal diligence translation was unavailable."),
                "why_not_now": english_safe_text(str(item.get("why_not_now") or ""), "A cleaner English rejection note was unavailable in this run."),
            }
            for item in payload.get("stage_one_candidates") or []
        ],
        "finalists": [
            {
                "company_name": _safe_company_label(item),
                "ticker": str(item.get("ticker") or "").strip(),
                "screen_score": item.get("screen_score"),
                "recommendation_rank": english_safe_text(str(item.get("recommendation_rank") or ""), "A"),
                "research_verdict": english_safe_text(str(item.get("research_verdict") or ""), "watchlist"),
                "confidence": english_safe_text(str(item.get("confidence") or ""), "medium"),
                "why_now": english_safe_text(str(item.get("why_now") or ""), "Why-now translation was unavailable for this finalist."),
                "why_not_now": english_safe_text(str(item.get("why_not_now") or ""), "A clearer English downgrade note was unavailable in this run."),
                "quick_take": english_safe_text(str(item.get("quick_take") or ""), "Quick take translation was unavailable in this run."),
                "vertical_summary": english_safe_text(str(item.get("vertical_summary") or ""), "Vertical diligence translation was unavailable."),
                "horizontal_summary": english_safe_text(str(item.get("horizontal_summary") or ""), "Horizontal diligence translation was unavailable."),
                "bull_bear_focus": english_safe_text(str(item.get("bull_bear_focus") or ""), "Bull/Bear focus translation was unavailable."),
                "short_term_target": english_safe_text(str(item.get("short_term_target") or ""), "n/a"),
                "document_path": str(item.get("document_path") or "").strip(),
            }
            for item in payload.get("finalists") or []
        ],
        "rejected": [
            {
                "label": english_safe_text(str(item.get("label") or ""), "candidate"),
                "reason": english_safe_text(str(item.get("reason") or ""), "English explanation was unavailable for this excluded name."),
            }
            for item in payload.get("rejected") or []
        ],
    }


def write_report_docx(path: Path, *, payload: dict[str, Any], language: str) -> None:
    labels = _report_labels(language)
    doc = _new_document()
    title = f"{payload.get('company_name') or payload.get('ticker')} {labels['memo_title']}"
    _add_title(doc, title, subtitle=f"{labels['ticker']}: {payload.get('ticker', '')} | {labels['market']}: {payload.get('market', '')}")
    _add_metadata_table(
        doc,
        [
            (labels["verdict"], str(payload.get("verdict") or "")),
            (labels["confidence"], str(payload.get("confidence") or "")),
            (labels["exchange"], str(payload.get("exchange") or "")),
            (labels["model"], str(payload.get("model") or "")),
        ],
    )
    _add_heading_and_paragraph(doc, labels["quick_take"], str(payload.get("quick_take") or ""))
    _add_heading_and_paragraph(doc, labels["business_summary"], str(payload.get("business_summary") or ""))
    _add_heading_and_paragraph(doc, labels["market_map"], str(payload.get("market_map") or ""))
    _add_heading_and_paragraph(doc, labels["china_story"], str(payload.get("china_story") or ""))
    _add_heading_and_paragraph(doc, labels["sentiment_simulation"], str(payload.get("sentiment_simulation") or ""))
    _add_heading_and_paragraph(doc, labels["peer_comparison"], str(payload.get("peer_comparison") or ""))
    _add_heading_and_paragraph(doc, labels["committee_takeaways"], str(payload.get("committee_takeaways") or ""))
    _add_heading_and_paragraph(doc, labels["scenario_outlook"], str(payload.get("scenario_outlook") or ""))
    _add_bullet_section(doc, labels["bull_case"], list(payload.get("bull_case") or []), labels["no_items"])
    _add_bullet_section(doc, labels["bear_case"], list(payload.get("bear_case") or []), labels["no_items"])
    _add_bullet_section(doc, labels["catalysts"], list(payload.get("catalysts") or []), labels["no_items"])
    _add_bullet_section(doc, labels["risks"], list(payload.get("risks") or []), labels["no_items"])
    _add_heading_and_paragraph(doc, labels["valuation_view"], str(payload.get("valuation_view") or ""))
    _add_target_price_section(doc, labels, payload.get("target_prices") or {})
    _add_heading_and_paragraph(doc, labels["debate_notes"], str(payload.get("debate_notes") or ""))
    _add_evidence_section(doc, labels, list(payload.get("evidence") or []))
    _add_bullet_section(doc, labels["next_questions"], list(payload.get("next_questions") or []), labels["no_items"])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def write_screening_docx(path: Path, *, payload: dict[str, Any], language: str) -> None:
    labels = _screening_labels(language)
    doc = _new_document()
    _add_title(doc, f"{payload.get('theme', '')} {labels['title']}", subtitle=f"{labels['market']}: {payload.get('market', '')}")
    finalists = list(payload.get("finalists") or [])
    stage_one = list(payload.get("stage_one_candidates") or [])
    _add_metadata_table(
        doc,
        [
            (labels["second_screen_pool"], str(len(stage_one))),
            (labels["final_recommendations"], str(len(finalists))),
        ],
    )
    doc.add_heading(labels["final_recommendations"], level=1)
    if not finalists:
        doc.add_paragraph(labels["no_items"])
    for item in finalists:
        doc.add_heading(f"{item.get('company_name') or item.get('ticker', '')} {item.get('ticker', '')}".strip(), level=2)
        for line in [
            f"{labels['recommendation_rank']}: {item.get('recommendation_rank') or 'A'}",
            f"{labels['screen_score']}: {item.get('screen_score') or 'n/a'}",
            f"{labels['research_verdict']}: {item.get('research_verdict') or 'watchlist'}",
            f"{labels['confidence']}: {item.get('confidence') or 'medium'}",
            f"{labels['why_now']}: {item.get('why_now') or labels['translation_unavailable']}",
            f"{labels['why_not_now']}: {item.get('why_not_now') or labels['translation_unavailable']}",
            f"{labels['quick_take']}: {item.get('quick_take') or labels['translation_unavailable']}",
            f"{labels['vertical_summary']}: {item.get('vertical_summary') or labels['translation_unavailable']}",
            f"{labels['horizontal_summary']}: {item.get('horizontal_summary') or labels['translation_unavailable']}",
            f"{labels['short_term_target']}: {item.get('short_term_target') or 'n/a'}",
            f"{labels['bull_bear_focus']}: {item.get('bull_bear_focus') or labels['translation_unavailable']}",
            f"{labels['document_path']}: {item.get('document_path') or 'n/a'}",
        ]:
            doc.add_paragraph(line, style="List Bullet")
    doc.add_heading(labels["downgraded_names"], level=1)
    rejected = list(payload.get("rejected") or [])
    if not rejected:
        doc.add_paragraph(labels["no_items"])
    for item in rejected:
        doc.add_paragraph(f"{item.get('label') or 'candidate'}: {item.get('reason') or labels['translation_unavailable']}", style="List Bullet")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def write_watchlist_digest_docx(path: Path, *, artifacts: list[dict[str, str]], language: str) -> None:
    labels = _digest_labels(language)
    doc = _new_document()
    _add_title(doc, labels["title"], subtitle=f"{labels['refreshed_names']}: {len(artifacts)}")
    if not artifacts:
        doc.add_paragraph(labels["no_items"])
    for item in artifacts:
        doc.add_heading(str(item.get("identifier") or "Name"), level=2)
        doc.add_paragraph(f"{labels['verdict']}: {item.get('verdict') or 'watchlist'}", style="List Bullet")
        doc.add_paragraph(f"{labels['target_snapshot']}: {item.get('target_snapshot') or 'n/a'}", style="List Bullet")
        path_key = "primary_document_path" if item.get("primary_document_path") else "zh_docx_path"
        doc.add_paragraph(f"{labels['document_path']}: {item.get(path_key) or 'n/a'}", style="List Bullet")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def summarize_bull_bear_for_doc(payload: dict[str, Any]) -> str:
    bull_case = list(payload.get("bull_case") or [])
    bear_case = list(payload.get("bear_case") or [])
    bull = bull_case[0] if bull_case else "bull case still needs verification"
    bear = bear_case[0] if bear_case else "bear case still needs verification"
    return f"Bull: {bull} | Bear: {bear}"


def _target_snapshot(targets: dict[str, Any], key: str) -> str:
    item = targets.get(key) or {}
    price = str(item.get("price") or "").strip() or "n/a"
    horizon = str(item.get("horizon") or "").strip() or "n/a"
    return f"{price} | {horizon}"


def _english_safe_list(value: Any, fallback: str) -> list[str]:
    if not isinstance(value, list):
        return [fallback]
    cleaned = [english_safe_text(str(item), fallback) for item in value if str(item).strip()]
    return cleaned or [fallback]


def _english_safe_evidence(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": english_safe_text(str(item.get("title") or ""), "Evidence source"),
                "url": str(item.get("url") or "").strip(),
                "claim": english_safe_text(str(item.get("claim") or ""), "Claim translation unavailable in this run."),
                "stance": english_safe_text(str(item.get("stance") or ""), "neutral"),
            }
        )
    return normalized


def _safe_company_label(item: dict[str, Any]) -> str:
    company_name = str(item.get("company_name") or "").strip()
    ticker = str(item.get("ticker") or "").strip()
    return ticker if contains_cjk(company_name) else (company_name or ticker or "candidate")


def _candidate_identity(item: dict[str, Any]) -> str:
    return str(item.get("ticker") or item.get("company_name") or "").strip()


def _new_document() -> Document:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.size = Pt(10.5)
    normal.font.name = "Arial"
    doc.sections[0].top_margin = Pt(48)
    doc.sections[0].bottom_margin = Pt(48)
    doc.sections[0].left_margin = Pt(54)
    doc.sections[0].right_margin = Pt(54)
    return doc


def _add_title(doc: Document, title: str, *, subtitle: str = "") -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run(title)
    run.bold = True
    run.font.size = Pt(18)
    if subtitle:
        sub = doc.add_paragraph(subtitle)
        sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
        sub.runs[0].italic = True
        sub.runs[0].font.size = Pt(9.5)


def _add_metadata_table(doc: Document, rows: list[tuple[str, str]]) -> None:
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        row = table.add_row().cells
        row[0].text = label
        row[1].text = value or "n/a"


def _add_heading_and_paragraph(doc: Document, heading: str, body: str) -> None:
    doc.add_heading(heading, level=1)
    cleaned = str(body or "").strip() or "-"
    for chunk in [part.strip() for part in cleaned.split("\n\n") if part.strip()]:
        doc.add_paragraph(chunk)


def _add_bullet_section(doc: Document, heading: str, items: list[str], empty_text: str) -> None:
    doc.add_heading(heading, level=1)
    if not items:
        doc.add_paragraph(empty_text)
        return
    for item in items:
        doc.add_paragraph(str(item), style="List Bullet")


def _add_target_price_section(doc: Document, labels: dict[str, str], target_prices: dict[str, dict[str, str]]) -> None:
    doc.add_heading(labels["target_prices"], level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    headers = table.rows[0].cells
    headers[0].text = labels["horizon"]
    headers[1].text = labels["price"]
    headers[2].text = labels["thesis"]
    for key, title in (
        ("short_term", labels["short_term"]),
        ("medium_term", labels["medium_term"]),
        ("long_term", labels["long_term"]),
    ):
        item = target_prices.get(key) or {}
        row = table.add_row().cells
        row[0].text = f"{title} | {item.get('horizon') or 'n/a'}"
        row[1].text = str(item.get("price") or "n/a")
        row[2].text = str(item.get("thesis") or labels["translation_unavailable"])


def _add_evidence_section(doc: Document, labels: dict[str, str], evidence: list[dict[str, str]]) -> None:
    doc.add_heading(labels["evidence"], level=1)
    if not evidence:
        doc.add_paragraph(labels["no_items"])
        return
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    headers = table.rows[0].cells
    headers[0].text = labels["source"]
    headers[1].text = labels["claim"]
    headers[2].text = labels["stance"]
    for item in evidence:
        row = table.add_row().cells
        row[0].text = f"{item.get('title') or 'Source'}\n{item.get('url') or ''}"
        row[1].text = str(item.get("claim") or "")
        row[2].text = str(item.get("stance") or "")


def _report_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "memo_title": "Buy-Side Research Memo",
            "ticker": "Ticker",
            "market": "Market",
            "verdict": "Verdict",
            "confidence": "Confidence",
            "exchange": "Exchange",
            "model": "Model",
            "quick_take": "Quick Take",
            "business_summary": "Business Summary",
            "market_map": "Market Map",
            "china_story": "Angle / Strategic Narrative",
            "sentiment_simulation": "Sentiment Simulation",
            "peer_comparison": "Peer Comparison",
            "committee_takeaways": "Guru Council Notes",
            "scenario_outlook": "Multi-Future Scenario Outlook",
            "bull_case": "Bull Case",
            "bear_case": "Bear Case",
            "catalysts": "Catalysts",
            "risks": "Risks",
            "valuation_view": "Valuation View",
            "target_prices": "Target Prices",
            "horizon": "Horizon",
            "price": "Target Price",
            "thesis": "Thesis",
            "debate_notes": "Red-Team Dissent",
            "evidence": "Evidence Checklist",
            "source": "Source",
            "claim": "Claim",
            "stance": "Stance",
            "next_questions": "Next Questions",
            "no_items": "No fully translated items were available in this run.",
            "short_term": "Short Term",
            "medium_term": "Medium Term",
            "long_term": "Long Term",
            "translation_unavailable": "Translation unavailable in this run.",
        }
    return {
        "memo_title": "研究备忘录",
        "ticker": "标的",
        "market": "市场",
        "verdict": "结论",
        "confidence": "信心",
        "exchange": "交易所",
        "model": "模型",
        "quick_take": "快速判断",
        "business_summary": "业务概览",
        "market_map": "市场与行业图谱",
        "china_story": "研究角度 / 叙事主线",
        "sentiment_simulation": "舆情与叙事模拟",
        "peer_comparison": "横向对比与估值锚",
        "committee_takeaways": "股神议会纪要",
        "scenario_outlook": "多未来场景",
        "bull_case": "多头逻辑",
        "bear_case": "空头逻辑",
        "catalysts": "催化剂",
        "risks": "主要风险",
        "valuation_view": "估值视角",
        "target_prices": "目标价与时间框架",
        "horizon": "时间",
        "price": "目标价",
        "thesis": "依据",
        "debate_notes": "投委会红队质询",
        "evidence": "证据清单",
        "source": "来源",
        "claim": "核心论点",
        "stance": "立场",
        "next_questions": "下一步验证问题",
        "no_items": "暂无充分结论，需继续补证。",
        "short_term": "短期",
        "medium_term": "中期",
        "long_term": "长期",
        "translation_unavailable": "当前证据仍不足，需要继续核实。",
    }


def _screening_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "title": "Screening Brief",
            "market": "Market",
            "second_screen_pool": "Second-Screen Pool",
            "final_recommendations": "Final Recommendations",
            "recommendation_rank": "Recommendation Rank",
            "screen_score": "Screen Score",
            "research_verdict": "Research Verdict",
            "confidence": "Confidence",
            "why_now": "Why Now",
            "why_not_now": "Why Not Now",
            "quick_take": "Quick Take",
            "vertical_summary": "Vertical Diligence",
            "horizontal_summary": "Horizontal Diligence",
            "short_term_target": "Short-Term Target",
            "bull_bear_focus": "Bull/Bear Focus",
            "document_path": "Report Document",
            "downgraded_names": "Downgraded or Excluded Names",
            "translation_unavailable": "English translation was unavailable in this run.",
            "no_items": "No items were available in this bucket.",
        }
    return {
        "title": "筛股报告",
        "market": "市场",
        "second_screen_pool": "二筛候选池",
        "final_recommendations": "最终推荐",
        "recommendation_rank": "推荐等级",
        "screen_score": "筛选分数",
        "research_verdict": "研究结论",
        "confidence": "信心",
        "why_now": "为什么现在值得看",
        "why_not_now": "为什么现在还不能下重注",
        "quick_take": "快速判断",
        "vertical_summary": "纵向尽调",
        "horizontal_summary": "横向尽调",
        "short_term_target": "短期目标价",
        "bull_bear_focus": "多空焦点",
        "document_path": "报告文档",
        "downgraded_names": "降级或淘汰名单",
        "translation_unavailable": "当前轮次还没有更清晰的补充说明。",
        "no_items": "当前桶里没有结果。",
    }


def _digest_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "title": "Watchlist Digest",
            "refreshed_names": "Refreshed Names",
            "verdict": "Verdict",
            "target_snapshot": "Target Snapshot",
            "document_path": "Report Document",
            "no_items": "No watchlist names were due in this cycle.",
        }
    return {
        "title": "跟踪池更新摘要",
        "refreshed_names": "本轮刷新标的数",
        "verdict": "结论",
        "target_snapshot": "目标价快照",
        "document_path": "报告文档",
        "no_items": "本轮没有到期需要刷新的标的。",
    }
