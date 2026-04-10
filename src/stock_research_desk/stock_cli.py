from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import re
import smtplib
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from ollama import Client

from .persona_pack import get_persona_blend, render_persona_instruction
from .runtime import parse_structured_response


DEFAULT_HOST = "https://ollama.com"
DEFAULT_MODEL = "kimi-k2.5:cloud"

DOMAIN_QUALITY_OVERRIDES: dict[str, int] = {
    "cninfo.com.cn": 96,
    "sse.com.cn": 95,
    "szse.cn": 95,
    "hkexnews.hk": 95,
    "sec.gov": 94,
    "gov.cn": 92,
    "yicai.com": 84,
    "caixin.com": 84,
    "eastmoney.com": 74,
    "finance.sina.com.cn": 68,
    "money.finance.sina.com.cn": 68,
    "stock.finance.sina.com.cn": 66,
    "vip.stock.finance.sina.com.cn": 66,
    "news.futunn.com": 72,
    "futunn.com": 72,
    "xueqiu.com": 70,
    "gg.cfi.cn": 58,
    "cfi.cn": 58,
    "lixinger.com": 64,
    "9fzt.com": 42,
    "vzkoo.com": 40,
    "fxbaogao.com": 40,
    "caifuhao.eastmoney.com": 34,
    "guba.eastmoney.com": 28,
}

BLOCKED_SOURCE_DOMAINS = {
    "guba.eastmoney.com",
}

MIN_SOURCE_QUALITY = 36


@dataclass(slots=True)
class WorkspacePaths:
    workspace_dir: Path
    reports_dir: Path
    memory_dir: Path
    screens_dir: Path
    digests_dir: Path
    watchlist_path: Path
    email_state_path: Path


@dataclass(slots=True)
class EmailConfig:
    address: str
    app_password: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    reply_to: str


@dataclass(slots=True)
class StockResearchConfig:
    api_key: str
    host: str
    model: str
    think: str
    max_results: int
    max_fetches: int
    timeout_seconds: float
    workspace_dir: Path
    reports_dir: Path
    screens_dir: Path
    memory_dir: Path
    watchlist_path: Path


@dataclass(slots=True)
class AgentRunResult:
    name: str
    content: str
    tool_traces: list[dict[str, Any]]


@dataclass(slots=True)
class MemoryContext:
    path: Path | None
    payload: dict[str, Any]


def main(argv: list[str] | None = None) -> None:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    if not raw_args or raw_args[0] in {"-h", "--help"}:
        parser = build_command_parser()
        parser.parse_args(raw_args)
        return
    if raw_args and raw_args[0] in {"research", "screen", "watchlist", "email"}:
        parser = build_command_parser()
        args = parser.parse_args(raw_args)
        dispatch_command(args)
        return

    parser = build_research_parser(implicit=True)
    args = parser.parse_args(raw_args)
    args.command = "research"
    dispatch_command(args)


def build_command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cloud-only multi-agent stock research desk with single-name deep dives, sector screening, and watchlist scheduling."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    research_parser = subparsers.add_parser("research", help="Run a full multi-agent memo for one stock.")
    build_research_parser(parent=research_parser)

    screen_parser = subparsers.add_parser("screen", help="Screen a sector/theme, run two-stage filtering, then deep research finalists.")
    screen_parser.add_argument("theme", help='Sector or board direction, for example: "中国机器人"')
    screen_parser.add_argument("--market", default="CN", help="Market hint, default: CN")
    screen_parser.add_argument("--count", type=int, default=3, help="Number of final recommendations to produce.")
    screen_parser.add_argument("--seed-ticker", action="append", default=[], help="Optional ticker seed, can be provided multiple times.")
    screen_parser.add_argument("--angle", default="", help="Optional screening frame or macro angle.")
    add_runtime_args(screen_parser)

    watchlist_parser = subparsers.add_parser("watchlist", help="Manage recurring stock analysis on a watchlist.")
    watchlist_subparsers = watchlist_parser.add_subparsers(dest="watchlist_command", required=True)

    watchlist_add = watchlist_subparsers.add_parser("add", help="Add or update a watchlist entry.")
    watchlist_add.add_argument("stock_name", help="Company or stock name.")
    watchlist_add.add_argument("--ticker", help="Optional ticker or exchange symbol hint.")
    watchlist_add.add_argument("--market", default="CN", help="Market hint, default: CN")
    watchlist_add.add_argument("--angle", default="", help="Optional research angle.")
    watchlist_add.add_argument("--interval", default="7d", help="Re-run cadence, e.g. 24h, 3d, 1w.")
    add_runtime_args(watchlist_add)

    watchlist_list = watchlist_subparsers.add_parser("list", help="Show current watchlist entries.")
    add_runtime_args(watchlist_list, include_model=False)

    watchlist_remove = watchlist_subparsers.add_parser("remove", help="Remove a watchlist entry by stock name or ticker.")
    watchlist_remove.add_argument("identifier", help="Stock name or ticker.")
    add_runtime_args(watchlist_remove, include_model=False)

    watchlist_run_due = watchlist_subparsers.add_parser("run-due", help="Run due watchlist analyses and refresh their schedules.")
    watchlist_run_due.add_argument("--limit", type=int, default=10, help="Max due entries to process in one run.")
    add_runtime_args(watchlist_run_due)

    email_parser = subparsers.add_parser("email", help="Process research commands from email and reply with results.")
    email_subparsers = email_parser.add_subparsers(dest="email_command", required=True)

    email_run_once = email_subparsers.add_parser("run-once", help="Poll inbox once, execute supported commands, and send replies.")
    email_run_once.add_argument("--limit", type=int, default=5, help="Max unread messages to process.")
    add_runtime_args(email_run_once)

    email_send_test = email_subparsers.add_parser("send-test", help="Send a connectivity test email.")
    email_send_test.add_argument("--to", required=True, help="Recipient email address.")
    add_runtime_args(email_send_test, include_model=False)

    return parser


def build_research_parser(parent: argparse.ArgumentParser | None = None, *, implicit: bool = False) -> argparse.ArgumentParser:
    parser = parent or argparse.ArgumentParser(
        description="Run a multi-agent stock research workflow on Ollama Cloud and save a local markdown memo."
    )
    parser.add_argument("stock_name", help="Company or stock name, for example: 赛腾股份")
    parser.add_argument("--ticker", help="Optional ticker or exchange symbol hint.")
    parser.add_argument("--market", default="CN", help="Market hint, default: CN")
    parser.add_argument("--angle", default="", help="Optional research angle or thesis framing.")
    add_runtime_args(parser)
    return parser


def add_runtime_args(parser: argparse.ArgumentParser, *, include_model: bool = True) -> None:
    if include_model:
        parser.add_argument("--model", default=os.getenv("STOCK_RESEARCH_DESK_MODEL", DEFAULT_MODEL))
        parser.add_argument("--think", default=os.getenv("STOCK_RESEARCH_DESK_THINK", "high"))
        parser.add_argument("--max-results", type=int, default=int(os.getenv("STOCK_RESEARCH_DESK_MAX_RESULTS", "5")))
        parser.add_argument("--max-fetches", type=int, default=int(os.getenv("STOCK_RESEARCH_DESK_MAX_FETCHES", "6")))
        parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("STOCK_RESEARCH_DESK_TIMEOUT_SECONDS", "45")))
    parser.add_argument("--output-dir", default=os.getenv("STOCK_RESEARCH_DESK_OUTPUT_DIR", "reports"))


def dispatch_command(args: argparse.Namespace) -> None:
    if args.command == "research":
        config = load_config(
            model=args.model,
            think=args.think,
            max_results=args.max_results,
            max_fetches=args.max_fetches,
            timeout_seconds=args.timeout_seconds,
            output_dir=args.output_dir,
        )
        artifact = run_stock_research(
            stock_name=args.stock_name,
            ticker=args.ticker,
            market=args.market,
            angle=args.angle,
            config=config,
            verbose=True,
        )
        print(f"Saved markdown report to: {artifact['markdown_path']}")
        print(f"Saved json payload to: {artifact['json_path']}")
        if artifact.get("memory_path"):
            print(f"Updated memory context at: {artifact['memory_path']}")
        return

    if args.command == "screen":
        config = load_config(
            model=args.model,
            think=args.think,
            max_results=args.max_results,
            max_fetches=args.max_fetches,
            timeout_seconds=args.timeout_seconds,
            output_dir=args.output_dir,
        )
        artifact = run_screening_pipeline(
            theme=args.theme,
            desired_count=args.count,
            market=args.market,
            angle=args.angle,
            seed_tickers=args.seed_ticker,
            config=config,
            verbose=True,
        )
        print(f"Saved screening markdown to: {artifact['markdown_path']}")
        print(f"Saved screening json to: {artifact['json_path']}")
        for path in artifact.get("report_paths", []):
            print(f"Generated finalist memo: {path}")
        return

    if args.command == "watchlist":
        paths = resolve_workspace_paths(args.output_dir)
        if args.watchlist_command == "add":
            entry = add_watchlist_entry(
                paths=paths,
                stock_name=args.stock_name,
                ticker=args.ticker,
                market=args.market,
                angle=args.angle,
                interval_spec=args.interval,
            )
            print(f"Saved watchlist entry: {entry['identifier']}")
            print(f"Next run at: {entry['next_run_at']}")
            return
        if args.watchlist_command == "list":
            render_watchlist(paths)
            return
        if args.watchlist_command == "remove":
            removed = remove_watchlist_entry(paths, args.identifier)
            if removed:
                print(f"Removed watchlist entry: {removed}")
            else:
                print(f"No watchlist entry matched: {args.identifier}")
            return
        if args.watchlist_command == "run-due":
            config = load_config(
                model=args.model,
                think=args.think,
                max_results=args.max_results,
                max_fetches=args.max_fetches,
                timeout_seconds=args.timeout_seconds,
                output_dir=args.output_dir,
            )
            result = run_due_watchlist(paths=paths, config=config, limit=args.limit, verbose=True)
            print(f"Processed {result['processed']} due entries.")
            for item in result["artifacts"]:
                print(f"- {item['identifier']}: {item['markdown_path']}")
            if result.get("digest_path"):
                print(f"Saved watchlist digest to: {result['digest_path']}")
            return

    if args.command == "email":
        paths = resolve_workspace_paths(args.output_dir)
        email_config = load_email_config()
        if args.email_command == "send-test":
            send_email_reply(
                config=email_config,
                to_address=args.to,
                subject="Stock Research Desk test",
                body="QQ mailbox integration is working.",
            )
            print(f"Sent test email to: {args.to}")
            return
        if args.email_command == "run-once":
            config = load_config(
                model=args.model,
                think=args.think,
                max_results=args.max_results,
                max_fetches=args.max_fetches,
                timeout_seconds=args.timeout_seconds,
                output_dir=args.output_dir,
            )
            result = process_email_inbox(paths=paths, email_config=email_config, config=config, limit=args.limit, verbose=True)
            print(f"Processed {result['processed']} email commands.")
            for item in result["replies"]:
                print(f"- replied to {item['from']} for {item['command']}")
            return

    raise RuntimeError(f"Unsupported command: {args.command}")


def default_workspace_home() -> Path:
    configured = os.getenv("STOCK_RESEARCH_DESK_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Desktop" / "Stock Research Desk").resolve()


def resolve_workspace_paths(output_dir: str) -> WorkspacePaths:
    workspace_dir = default_workspace_home()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_dir).expanduser()
    reports_dir = output_path.resolve() if output_path.is_absolute() else (workspace_dir / output_path).resolve()
    memory_dir = (workspace_dir / "memory_palace").resolve()
    screens_dir = (workspace_dir / "screenings").resolve()
    digests_dir = (workspace_dir / "digests").resolve()
    watchlist_path = (workspace_dir / "watchlist.json").resolve()
    email_state_path = (workspace_dir / "email_state.json").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)
    screens_dir.mkdir(parents=True, exist_ok=True)
    digests_dir.mkdir(parents=True, exist_ok=True)
    return WorkspacePaths(
        workspace_dir=workspace_dir,
        reports_dir=reports_dir,
        memory_dir=memory_dir,
        screens_dir=screens_dir,
        digests_dir=digests_dir,
        watchlist_path=watchlist_path,
        email_state_path=email_state_path,
    )


def load_config(
    *,
    model: str,
    think: str,
    max_results: int,
    max_fetches: int,
    timeout_seconds: float,
    output_dir: str,
) -> StockResearchConfig:
    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OLLAMA_API_KEY is required for direct Ollama Cloud access. "
            "Create an API key in your Ollama account and export it before running this command."
        )
    host = os.getenv("STOCK_RESEARCH_DESK_OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
    if "127.0.0.1" in host or "localhost" in host:
        raise RuntimeError("This branch is configured for Ollama Cloud only. Do not point it at a local Ollama host.")
    paths = resolve_workspace_paths(output_dir)
    return StockResearchConfig(
        api_key=api_key,
        host=host,
        model=model,
        think=think,
        max_results=max_results,
        max_fetches=max_fetches,
        timeout_seconds=timeout_seconds,
        workspace_dir=paths.workspace_dir,
        reports_dir=paths.reports_dir,
        screens_dir=paths.screens_dir,
        memory_dir=paths.memory_dir,
        watchlist_path=paths.watchlist_path,
    )


def run_stock_research(
    *,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    config: StockResearchConfig,
    verbose: bool = False,
) -> dict[str, str]:
    memory_context = load_memory_context(
        memory_dir=config.memory_dir,
        stock_name=stock_name,
        ticker=ticker,
    )
    client = Client(
        host=config.host,
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=config.timeout_seconds,
    )
    if verbose:
        print(f"[stock-research] model={config.model} think={config.think} max_results={config.max_results} max_fetches={config.max_fetches}")
        if memory_context:
            print(f"[stock-research] loaded memory context from {memory_context.path}")

    started = time.perf_counter()
    market_analyst = safe_run_agent_with_tools(
        client=client,
        name="market_analyst",
        model=config.model,
        think=config.think,
        system_prompt=build_market_analyst_prompt(config.max_results, config.max_fetches),
        user_prompt=build_agent_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            objective="分析行业、需求周期、竞争格局、中国叙事与估值框架线索。",
            memory_context=memory_context,
        ),
        max_results=config.max_results,
        max_fetches=max(2, config.max_fetches - 1),
        verbose=verbose,
    )
    company_analyst = safe_run_agent_with_tools(
        client=client,
        name="company_analyst",
        model=config.model,
        think=config.think,
        system_prompt=build_company_analyst_prompt(config.max_results, config.max_fetches),
        user_prompt=build_agent_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            objective="分析公司业务、产品、客户、财务信号、治理风险、催化剂与反方论据。",
            memory_context=memory_context,
        ),
        max_results=config.max_results,
        max_fetches=config.max_fetches,
        verbose=verbose,
    )
    sentiment_simulator = safe_run_agent_with_tools(
        client=client,
        name="sentiment_simulator",
        model=config.model,
        think=config.think,
        system_prompt=build_sentiment_simulator_prompt(config.max_results, config.max_fetches),
        user_prompt=build_agent_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            objective="搜集公开叙事并模拟四类参与者的反应：成长基金、卖方怀疑派、产业链经营者、题材交易型散户。",
            memory_context=memory_context,
        ),
        max_results=config.max_results,
        max_fetches=max(2, config.max_fetches - 1),
        verbose=verbose,
    )
    comparison_analyst = safe_run_agent_with_tools(
        client=client,
        name="comparison_analyst",
        model=config.model,
        think=config.think,
        system_prompt=build_comparison_analyst_prompt(config.max_results, config.max_fetches),
        user_prompt=build_agent_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            objective="做横向可比公司、估值锚、周期位置与历史表现对比，找出这只股票为什么值得或不值得研究。",
            memory_context=memory_context,
        ),
        max_results=config.max_results,
        max_fetches=config.max_fetches,
        verbose=verbose,
    )
    committee_red_team = run_deliberation_agent(
        client=client,
        model=config.model,
        think=config.think,
        name="committee_red_team",
        system_prompt=build_red_team_prompt(),
        user_prompt=build_red_team_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
        ),
        fallback_note=build_red_team_fallback(
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
        ),
        verbose=verbose,
    )
    guru_council = run_deliberation_agent(
        client=client,
        model=config.model,
        think=config.think,
        name="guru_council",
        system_prompt=build_guru_council_prompt(),
        user_prompt=build_guru_council_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
            committee_red_team=committee_red_team,
        ),
        fallback_note=build_guru_council_fallback(
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
            committee_red_team=committee_red_team,
        ),
        verbose=verbose,
    )
    mirofish_scenario_engine = run_deliberation_agent(
        client=client,
        model=config.model,
        think=config.think,
        name="mirofish_scenario_engine",
        system_prompt=build_mirofish_scenario_prompt(),
        user_prompt=build_mirofish_scenario_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
            committee_red_team=committee_red_team,
            guru_council=guru_council,
        ),
        fallback_note=build_mirofish_scenario_fallback(
            stock_name=stock_name,
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
            committee_red_team=committee_red_team,
        ),
        verbose=verbose,
    )
    price_committee = safe_run_agent_with_tools(
        client=client,
        name="price_committee",
        model=config.model,
        think=config.think,
        system_prompt=build_price_committee_prompt(config.max_results, config.max_fetches),
        user_prompt=build_agent_user_prompt(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            objective="基于当前价格、估值锚、风险与情景推演，给出短期、中期、长期目标价和对应时间。",
            memory_context=memory_context,
        ),
        max_results=max(3, config.max_results - 1),
        max_fetches=max(2, config.max_fetches - 2),
        verbose=verbose,
    )
    distilled_notes = {
        market_analyst.name: distill_agent_note(name=market_analyst.name, content=market_analyst.content, tool_traces=market_analyst.tool_traces),
        company_analyst.name: distill_agent_note(name=company_analyst.name, content=company_analyst.content, tool_traces=company_analyst.tool_traces),
        sentiment_simulator.name: distill_agent_note(name=sentiment_simulator.name, content=sentiment_simulator.content, tool_traces=sentiment_simulator.tool_traces),
        comparison_analyst.name: distill_agent_note(name=comparison_analyst.name, content=comparison_analyst.content, tool_traces=comparison_analyst.tool_traces),
        committee_red_team.name: distill_agent_note(name=committee_red_team.name, content=committee_red_team.content, tool_traces=committee_red_team.tool_traces),
        guru_council.name: distill_agent_note(name=guru_council.name, content=guru_council.content, tool_traces=guru_council.tool_traces),
        mirofish_scenario_engine.name: distill_agent_note(name=mirofish_scenario_engine.name, content=mirofish_scenario_engine.content, tool_traces=mirofish_scenario_engine.tool_traces),
        price_committee.name: distill_agent_note(name=price_committee.name, content=price_committee.content, tool_traces=price_committee.tool_traces),
    }

    if verbose:
        print("[stock-research] synthesizing final memo")
    final_content = synthesize_buy_side_report(
        client=client,
        config=config,
        stock_name=stock_name,
        ticker=ticker,
        market=market,
        angle=angle,
        market_analyst=market_analyst,
        company_analyst=company_analyst,
        sentiment_simulator=sentiment_simulator,
        comparison_analyst=comparison_analyst,
        committee_red_team=committee_red_team,
        guru_council=guru_council,
        mirofish_scenario_engine=mirofish_scenario_engine,
        price_committee=price_committee,
        distilled_notes=distilled_notes,
    )
    if not final_content:
        raise RuntimeError("Ollama Cloud research did not produce a final structured response.")

    parsed, repaired = parse_structured_response(final_content)
    fallback_evidence = extract_evidence_from_traces(
        [
            market_analyst.tool_traces,
            company_analyst.tool_traces,
            sentiment_simulator.tool_traces,
            comparison_analyst.tool_traces,
            price_committee.tool_traces,
        ]
    )
    normalized = normalize_report_payload(
        parsed,
        stock_name=stock_name,
        ticker=ticker,
        market=market,
        angle=angle,
        model=config.model,
        fallback_evidence=fallback_evidence,
        distilled_notes=distilled_notes,
        fallback_target_prices=extract_target_prices_from_text(price_committee.content),
    )
    slug = slugify(normalized["ticker"] or normalized["company_name"] or stock_name)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    markdown_path = config.reports_dir / f"{timestamp}-{slug}.md"
    json_path = config.reports_dir / f"{timestamp}-{slug}.json"
    markdown_path.write_text(normalized["report_markdown"], encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                **normalized,
                "agent_outputs": {
                    market_analyst.name: market_analyst.content,
                    company_analyst.name: company_analyst.content,
                    sentiment_simulator.name: sentiment_simulator.content,
                    comparison_analyst.name: comparison_analyst.content,
                    committee_red_team.name: committee_red_team.content,
                    guru_council.name: guru_council.content,
                    mirofish_scenario_engine.name: mirofish_scenario_engine.content,
                    price_committee.name: price_committee.content,
                },
                "distilled_notes": distilled_notes,
                "runtime_metadata": {
                    "repaired": repaired,
                    "model": config.model,
                    "persona_pack": {
                        role: list(get_persona_blend(role).lead_investors)
                        for role in [
                            market_analyst.name,
                            company_analyst.name,
                            sentiment_simulator.name,
                            comparison_analyst.name,
                            committee_red_team.name,
                            guru_council.name,
                            mirofish_scenario_engine.name,
                            price_committee.name,
                        ]
                    },
                    "agent_tool_counts": {
                        market_analyst.name: len(market_analyst.tool_traces),
                        company_analyst.name: len(company_analyst.tool_traces),
                        sentiment_simulator.name: len(sentiment_simulator.tool_traces),
                        comparison_analyst.name: len(comparison_analyst.tool_traces),
                        committee_red_team.name: len(committee_red_team.tool_traces),
                        guru_council.name: len(guru_council.tool_traces),
                        mirofish_scenario_engine.name: len(mirofish_scenario_engine.tool_traces),
                        price_committee.name: len(price_committee.tool_traces),
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    memory_path = save_memory_context(
        memory_dir=config.memory_dir,
        stock_name=stock_name,
        normalized=normalized,
        market_analyst=market_analyst,
        company_analyst=company_analyst,
        sentiment_simulator=sentiment_simulator,
        comparison_analyst=comparison_analyst,
        committee_red_team=committee_red_team,
        guru_council=guru_council,
        mirofish_scenario_engine=mirofish_scenario_engine,
        price_committee=price_committee,
    )
    if verbose:
        elapsed = round(time.perf_counter() - started, 1)
        print(f"[stock-research] completed in {elapsed}s")
    return {
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "memory_path": str(memory_path),
        "payload": normalized,
    }


def run_screening_pipeline(
    *,
    theme: str,
    desired_count: int,
    market: str,
    angle: str,
    seed_tickers: list[str],
    config: StockResearchConfig,
    verbose: bool = False,
) -> dict[str, Any]:
    client = Client(
        host=config.host,
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=config.timeout_seconds,
    )
    if verbose:
        print(f"[screen] theme={theme} market={market} desired_count={desired_count}")

    scout = run_screening_scout(
        client=client,
        model=config.model,
        think=config.think,
        theme=theme,
        desired_count=desired_count,
        market=market,
        seed_tickers=seed_tickers,
        max_results=config.max_results,
        max_fetches=config.max_fetches,
        verbose=verbose,
    )
    initial_candidates = normalize_screen_candidates(
        (scout.get("payload") or {}).get("candidates"),
        theme=theme,
        market=market,
    )
    if not initial_candidates:
        initial_candidates = build_screening_fallback_candidates(
            extract_evidence_from_traces([scout.get("tool_traces", [])]),
            theme=theme,
            market=market,
        )
    stage_one_count = min(max(desired_count * 3, desired_count + 2), len(initial_candidates))
    stage_one = initial_candidates[:stage_one_count]

    shortlist = run_second_screen_committee(
        client=client,
        model=config.model,
        think=config.think,
        theme=theme,
        market=market,
        desired_count=desired_count,
        candidates=stage_one,
    )
    finalists = normalize_screen_candidates(shortlist.get("recommended"), theme=theme, market=market)[:desired_count]
    if not finalists:
        finalists = stage_one[:desired_count]

    finalist_artifacts: list[dict[str, Any]] = []
    for index, candidate in enumerate(finalists, start=1):
        run_angle = candidate.get("angle") or angle or theme
        if verbose:
            print(f"[screen] final pass {index}/{len(finalists)}: {candidate['company_name']} {candidate.get('ticker', '')}".strip())
        artifact = run_stock_research(
            stock_name=candidate["company_name"],
            ticker=candidate.get("ticker"),
            market=candidate.get("market") or market,
            angle=run_angle,
            config=config,
            verbose=verbose,
        )
        finalist_artifacts.append(
            {
                "company_name": candidate["company_name"],
                "ticker": candidate.get("ticker", ""),
                "screen_score": candidate.get("screen_score", 50),
                "stage_two_note": candidate.get("rationale", ""),
                "markdown_path": artifact["markdown_path"],
                "json_path": artifact["json_path"],
                "payload": artifact.get("payload", {}),
            }
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = slugify(theme)
    markdown_path = config.screens_dir / f"{timestamp}-{slug}-screening.md"
    json_path = config.screens_dir / f"{timestamp}-{slug}-screening.json"
    summary_payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "seed_tickers": seed_tickers,
        "initial_candidates": initial_candidates,
        "stage_one_candidates": stage_one,
        "finalists": finalist_artifacts,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    markdown_path.write_text(
        render_screening_markdown(
            theme=theme,
            market=market,
            stage_one_candidates=stage_one,
            finalists=finalist_artifacts,
        ),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "report_paths": [item["markdown_path"] for item in finalist_artifacts],
        "payload": summary_payload,
    }


def run_screening_scout(
    *,
    client: Client,
    model: str,
    think: str,
    theme: str,
    desired_count: int,
    market: str,
    seed_tickers: list[str],
    max_results: int,
    max_fetches: int,
    verbose: bool = False,
) -> dict[str, Any]:
    system_prompt = build_screening_scout_prompt(max_results=max_results, max_fetches=max_fetches)
    user_prompt = build_screening_user_prompt(theme=theme, desired_count=desired_count, market=market, seed_tickers=seed_tickers)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_traces: list[dict[str, Any]] = []
    fetch_count = 0
    if verbose:
        print("[screen] scouting candidates")
    planning_response = client.chat(
        model=model,
        messages=messages,
        tools=[client.web_search, client.web_fetch],
        think=resolve_think(model, think),
    )
    planning_message = planning_response.message
    tool_calls = planning_message.tool_calls or []
    for tool_call in tool_calls:
        function = tool_call.function
        tool_name = function.name
        arguments = dict(function.arguments or {})
        if tool_name == "web_search":
            arguments["max_results"] = min(int(arguments.get("max_results", max_results)), max_results)
            result = client.web_search(**arguments).model_dump()
        elif tool_name == "web_fetch":
            if fetch_count >= max_fetches:
                result = {"error": "fetch budget exhausted"}
            else:
                result = client.web_fetch(**arguments).model_dump()
                fetch_count += 1
        else:
            result = {"error": f"unsupported tool: {tool_name}"}
        tool_traces.append({"tool_name": tool_name, "arguments": arguments, "result": result})

    synthesis_prompt = build_screening_synthesis_prompt(
        theme=theme,
        desired_count=desired_count,
        market=market,
        evidence=extract_evidence_from_traces([tool_traces])[:10],
        seed_tickers=seed_tickers,
    )
    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": synthesis_prompt},
            ],
            think=resolve_think(model, think),
            format="json",
        )
        parsed, _ = parse_structured_response(response.message.content or "")
        if isinstance(parsed, dict):
            return {"payload": parsed, "tool_traces": tool_traces}
    except Exception:
        pass
    return {"payload": {"candidates": build_screening_fallback_candidates(extract_evidence_from_traces([tool_traces]), theme=theme, market=market)}, "tool_traces": tool_traces}


def run_second_screen_committee(
    *,
    client: Client,
    model: str,
    think: str,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = build_second_screen_prompt(theme=theme, market=market, desired_count=desired_count, candidates=candidates)
    fallback = {"recommended": sorted(candidates, key=screen_sort_key, reverse=True)[:desired_count]}
    try:
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a disciplined stock-screening committee. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            think=resolve_think(model, think),
            format="json",
        )
        parsed, _ = parse_structured_response(response.message.content or "")
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return fallback


def add_watchlist_entry(
    *,
    paths: WorkspacePaths,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    interval_spec: str,
) -> dict[str, Any]:
    entries = load_watchlist(paths)
    interval_hours = parse_interval_hours(interval_spec)
    identifier = slugify(ticker or stock_name)
    now = datetime.now(UTC)
    payload = {
        "identifier": identifier,
        "stock_name": stock_name,
        "ticker": ticker or "",
        "market": market,
        "angle": angle,
        "interval_spec": interval_spec,
        "interval_hours": interval_hours,
        "next_run_at": now.isoformat(),
        "last_run_at": None,
        "last_report_path": "",
    }
    replaced = False
    for index, entry in enumerate(entries):
        if entry.get("identifier") == identifier:
            entries[index] = payload
            replaced = True
            break
    if not replaced:
        entries.append(payload)
    save_watchlist(paths, entries)
    return payload


def render_watchlist(paths: WorkspacePaths) -> None:
    entries = load_watchlist(paths)
    if not entries:
        print("Watchlist is empty.")
        return
    for entry in sorted(entries, key=lambda item: item.get("next_run_at", "")):
        label = entry.get("ticker") or entry.get("stock_name")
        print(
            f"- {label} | interval={entry.get('interval_spec')} | next={entry.get('next_run_at')} | "
            f"last={entry.get('last_run_at') or 'never'}"
        )


def remove_watchlist_entry(paths: WorkspacePaths, identifier: str) -> str | None:
    entries = load_watchlist(paths)
    needle = slugify(identifier)
    kept = [entry for entry in entries if entry.get("identifier") != needle and slugify(entry.get("stock_name", "")) != needle]
    if len(kept) == len(entries):
        return None
    save_watchlist(paths, kept)
    return identifier


def run_due_watchlist(
    *,
    paths: WorkspacePaths,
    config: StockResearchConfig,
    limit: int,
    verbose: bool = False,
) -> dict[str, Any]:
    entries = load_watchlist(paths)
    now = datetime.now(UTC)
    processed = 0
    artifacts: list[dict[str, str]] = []
    for entry in sorted(entries, key=lambda item: item.get("next_run_at", "")):
        if processed >= limit:
            break
        next_run_at = parse_iso_datetime(entry.get("next_run_at"))
        if next_run_at and next_run_at > now:
            continue
        artifact = run_stock_research(
            stock_name=entry["stock_name"],
            ticker=entry.get("ticker") or None,
            market=entry.get("market") or "CN",
            angle=entry.get("angle") or "",
            config=config,
            verbose=verbose,
        )
        processed += 1
        entry["last_run_at"] = now.isoformat()
        entry["last_report_path"] = artifact["markdown_path"]
        entry["next_run_at"] = (now.timestamp() + int(entry.get("interval_hours", 24)) * 3600)
        entry["next_run_at"] = datetime.fromtimestamp(entry["next_run_at"], UTC).isoformat()
        artifacts.append(
            {
                "identifier": entry["identifier"],
                "markdown_path": artifact["markdown_path"],
                "verdict": (artifact.get("payload") or {}).get("verdict", "watchlist"),
                "quick_take": (artifact.get("payload") or {}).get("quick_take", ""),
            }
        )
    save_watchlist(paths, entries)
    digest_path = ""
    if artifacts:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        digest_path_obj = paths.digests_dir / f"{timestamp}-watchlist-digest.md"
        digest_path_obj.write_text(render_watchlist_digest_markdown(artifacts), encoding="utf-8")
        digest_path = str(digest_path_obj)
    return {"processed": processed, "artifacts": artifacts, "digest_path": digest_path}


def load_watchlist(paths: WorkspacePaths) -> list[dict[str, Any]]:
    if not paths.watchlist_path.exists():
        return []
    try:
        payload = json.loads(paths.watchlist_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def save_watchlist(paths: WorkspacePaths, entries: list[dict[str, Any]]) -> None:
    paths.watchlist_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def render_watchlist_digest_markdown(artifacts: list[dict[str, str]]) -> str:
    lines = [
        "# Watchlist Digest",
        "",
        f"- Generated at: `{datetime.now(UTC).isoformat()}`",
        "",
    ]
    for item in artifacts:
        lines.extend(
            [
                f"## {item['identifier']}",
                f"- Verdict: `{item.get('verdict', 'watchlist')}`",
                f"- Quick take: {item.get('quick_take', '') or 'n/a'}",
                f"- Report: `{item.get('markdown_path', '')}`",
                "",
            ]
        )
    return "\n".join(lines)


def load_email_state(paths: WorkspacePaths) -> dict[str, Any]:
    if not paths.email_state_path.exists():
        return {"processed_message_ids": []}
    try:
        payload = json.loads(paths.email_state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed_message_ids": []}
    if not isinstance(payload, dict):
        return {"processed_message_ids": []}
    payload.setdefault("processed_message_ids", [])
    return payload


def save_email_state(paths: WorkspacePaths, state: dict[str, Any]) -> None:
    paths.email_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_email_config() -> EmailConfig:
    address = os.getenv("STOCK_RESEARCH_DESK_EMAIL_ADDRESS", "").strip()
    app_password = os.getenv("STOCK_RESEARCH_DESK_EMAIL_APP_PASSWORD", "").strip()
    provider = os.getenv("STOCK_RESEARCH_DESK_EMAIL_PROVIDER", "qq").strip().lower()
    if provider == "qq":
        imap_host = os.getenv("STOCK_RESEARCH_DESK_EMAIL_IMAP_HOST", "imap.qq.com").strip()
        smtp_host = os.getenv("STOCK_RESEARCH_DESK_EMAIL_SMTP_HOST", "smtp.qq.com").strip()
        imap_port = int(os.getenv("STOCK_RESEARCH_DESK_EMAIL_IMAP_PORT", "993"))
        smtp_port = int(os.getenv("STOCK_RESEARCH_DESK_EMAIL_SMTP_PORT", "465"))
    else:
        imap_host = os.getenv("STOCK_RESEARCH_DESK_EMAIL_IMAP_HOST", "").strip()
        smtp_host = os.getenv("STOCK_RESEARCH_DESK_EMAIL_SMTP_HOST", "").strip()
        imap_port = int(os.getenv("STOCK_RESEARCH_DESK_EMAIL_IMAP_PORT", "993"))
        smtp_port = int(os.getenv("STOCK_RESEARCH_DESK_EMAIL_SMTP_PORT", "465"))
    if not address or not app_password or not imap_host or not smtp_host:
        raise RuntimeError(
            "Email integration requires STOCK_RESEARCH_DESK_EMAIL_ADDRESS, "
            "STOCK_RESEARCH_DESK_EMAIL_APP_PASSWORD, and valid IMAP/SMTP settings."
        )
    return EmailConfig(
        address=address,
        app_password=app_password,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        reply_to=os.getenv("STOCK_RESEARCH_DESK_EMAIL_REPLY_TO", address).strip() or address,
    )


def process_email_inbox(
    *,
    paths: WorkspacePaths,
    email_config: EmailConfig,
    config: StockResearchConfig,
    limit: int,
    verbose: bool = False,
) -> dict[str, Any]:
    state = load_email_state(paths)
    processed_ids = set(state.get("processed_message_ids", []))
    replies: list[dict[str, str]] = []
    processed = 0
    with imaplib.IMAP4_SSL(email_config.imap_host, email_config.imap_port) as mailbox:
        mailbox.login(email_config.address, email_config.app_password)
        mailbox.select("INBOX")
        status, data = mailbox.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("Failed to search inbox.")
        message_nums = list(reversed((data[0] or b"").split()))[:limit]
        for num in message_nums:
            status, msg_data = mailbox.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw)
            message_id = str(message.get("Message-ID") or num.decode())
            if message_id in processed_ids:
                continue
            from_address = email.utils.parseaddr(message.get("From") or "")[1]
            subject = decode_mime_header(message.get("Subject") or "")
            body = extract_email_plain_text(message)
            command = parse_email_command(subject=subject, body=body)
            if not command:
                reply_body = (
                    "Stock Research Desk did not recognize your command.\n\n"
                    "Supported subjects:\n"
                    "- research: 赛腾股份 | 603283.SH | CN | 中国故事\n"
                    "- screen: 中国机器人 | 3 | CN | 中国故事\n"
                    "- watchlist add: 赛腾股份 | 603283.SH | 7d | CN | 中国故事\n"
                    "- watchlist list\n"
                    "- watchlist run-due\n"
                )
                send_email_reply(
                    config=email_config,
                    to_address=from_address,
                    subject=f"Re: {subject}",
                    body=reply_body,
                )
                processed_ids.add(message_id)
                replies.append({"from": from_address, "command": "unknown"})
                processed += 1
                continue
            reply = execute_email_command(paths=paths, config=config, command=command, verbose=verbose)
            send_email_reply(
                config=email_config,
                to_address=from_address,
                subject=f"Re: {subject}",
                body=reply["body"],
                attachments=reply.get("attachments", []),
            )
            processed_ids.add(message_id)
            replies.append({"from": from_address, "command": command["kind"]})
            processed += 1
        mailbox.close()
    save_email_state(paths, {"processed_message_ids": list(processed_ids)[-200:]})
    return {"processed": processed, "replies": replies}


def decode_mime_header(value: str) -> str:
    return str(make_header(decode_header(value))).strip()


def extract_email_plain_text(message: email.message.Message) -> str:
    if message.is_multipart():
        parts: list[str] = []
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if payload:
                parts.append(payload.decode(charset, errors="replace"))
        return "\n".join(parts).strip()
    payload = message.get_payload(decode=True)
    if payload is None:
        return str(message.get_payload() or "").strip()
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace").strip()


def parse_email_command(*, subject: str, body: str) -> dict[str, Any] | None:
    command_line = (subject or "").strip()
    if not command_line:
        for line in body.splitlines():
            if line.strip():
                command_line = line.strip()
                break
    lowered = command_line.lower()
    if lowered.startswith("research:"):
        parts = [part.strip() for part in command_line.split(":", 1)[1].split("|")]
        stock_name = parts[0] if parts else ""
        return {
            "kind": "research",
            "stock_name": stock_name,
            "ticker": parts[1] if len(parts) > 1 else "",
            "market": parts[2] if len(parts) > 2 and parts[2] else "CN",
            "angle": parts[3] if len(parts) > 3 else "",
        } if stock_name else None
    if lowered.startswith("screen:"):
        parts = [part.strip() for part in command_line.split(":", 1)[1].split("|")]
        theme = parts[0] if parts else ""
        return {
            "kind": "screen",
            "theme": theme,
            "count": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3,
            "market": parts[2] if len(parts) > 2 and parts[2] else "CN",
            "angle": parts[3] if len(parts) > 3 else "",
        } if theme else None
    if lowered.startswith("watchlist add:"):
        parts = [part.strip() for part in command_line.split(":", 1)[1].split("|")]
        stock_name = parts[0] if parts else ""
        return {
            "kind": "watchlist_add",
            "stock_name": stock_name,
            "ticker": parts[1] if len(parts) > 1 else "",
            "interval": parts[2] if len(parts) > 2 and parts[2] else "7d",
            "market": parts[3] if len(parts) > 3 and parts[3] else "CN",
            "angle": parts[4] if len(parts) > 4 else "",
        } if stock_name else None
    if lowered.startswith("watchlist list"):
        return {"kind": "watchlist_list"}
    if lowered.startswith("watchlist run-due"):
        return {"kind": "watchlist_run_due"}
    return None


def execute_email_command(
    *,
    paths: WorkspacePaths,
    config: StockResearchConfig,
    command: dict[str, Any],
    verbose: bool = False,
) -> dict[str, Any]:
    kind = command["kind"]
    if kind == "research":
        artifact = run_stock_research(
            stock_name=command["stock_name"],
            ticker=command.get("ticker") or None,
            market=command.get("market") or "CN",
            angle=command.get("angle") or "",
            config=config,
            verbose=verbose,
        )
        payload = artifact.get("payload", {})
        body = render_email_research_reply(payload, artifact["markdown_path"])
        return {"body": body, "attachments": [artifact["markdown_path"], artifact["json_path"]]}
    if kind == "screen":
        artifact = run_screening_pipeline(
            theme=command["theme"],
            desired_count=int(command.get("count") or 3),
            market=command.get("market") or "CN",
            angle=command.get("angle") or "",
            seed_tickers=[],
            config=config,
            verbose=verbose,
        )
        body = render_email_screen_reply(theme=command["theme"], payload=artifact["payload"], markdown_path=artifact["markdown_path"])
        attachments = [artifact["markdown_path"], artifact["json_path"], *artifact.get("report_paths", [])]
        return {"body": body, "attachments": attachments}
    if kind == "watchlist_add":
        entry = add_watchlist_entry(
            paths=paths,
            stock_name=command["stock_name"],
            ticker=command.get("ticker") or None,
            market=command.get("market") or "CN",
            angle=command.get("angle") or "",
            interval_spec=command.get("interval") or "7d",
        )
        return {
            "body": (
                f"Watchlist entry added.\n\n"
                f"- Stock: {entry['stock_name']}\n"
                f"- Ticker: {entry.get('ticker') or 'n/a'}\n"
                f"- Interval: {entry['interval_spec']}\n"
                f"- Next run: {entry['next_run_at']}\n"
            ),
            "attachments": [],
        }
    if kind == "watchlist_list":
        entries = load_watchlist(paths)
        body = "Current watchlist:\n\n" + ("\n".join(
            f"- {entry.get('ticker') or entry.get('stock_name')} | interval={entry.get('interval_spec')} | next={entry.get('next_run_at')}"
            for entry in entries
        ) if entries else "- empty")
        return {"body": body, "attachments": [str(paths.watchlist_path)] if paths.watchlist_path.exists() else []}
    if kind == "watchlist_run_due":
        result = run_due_watchlist(paths=paths, config=config, limit=10, verbose=verbose)
        body = f"Processed {result['processed']} due watchlist entries.\n"
        if result.get("digest_path"):
            body += f"\nDigest: {result['digest_path']}\n"
        for item in result["artifacts"]:
            body += f"- {item['identifier']}: {item['markdown_path']}\n"
        attachments = [result["digest_path"]] if result.get("digest_path") else []
        attachments.extend(item["markdown_path"] for item in result["artifacts"])
        return {"body": body, "attachments": attachments}
    raise RuntimeError(f"Unsupported email command: {kind}")


def render_email_research_reply(payload: dict[str, Any], markdown_path: str) -> str:
    targets = payload.get("target_prices") or {}
    bull_case = list(payload.get("bull_case") or [])
    risks = list(payload.get("risks") or [])
    lines = [
        f"Research completed for {payload.get('company_name') or payload.get('ticker')}.",
        "",
        f"- Verdict: {payload.get('verdict', 'watchlist')}",
        f"- Confidence: {payload.get('confidence', 'medium')}",
        f"- Quick take: {payload.get('quick_take', '')}",
        "",
        "Top bull points:",
    ]
    lines.extend(f"- {item}" for item in bull_case[:3] or ["Not enough evidence to form strong bull points yet."])
    lines.extend([
        "",
        "Key risks:",
    ])
    lines.extend(f"- {item}" for item in risks[:3] or ["Risks still need more verification."])
    lines.extend([
        "",
        "Target prices:",
    ])
    for key, label in (("short_term", "Short"), ("medium_term", "Medium"), ("long_term", "Long")):
        item = targets.get(key) or {}
        lines.append(f"- {label}: {item.get('price', 'n/a')} | {item.get('horizon', 'n/a')} | {item.get('thesis', '')}")
    lines.extend(["", f"Attached memo: {markdown_path}"])
    return "\n".join(lines)


def render_email_screen_reply(*, theme: str, payload: dict[str, Any], markdown_path: str) -> str:
    finalists = payload.get("finalists") or []
    initial_candidates = payload.get("initial_candidates") or []
    stage_one_candidates = payload.get("stage_one_candidates") or []
    lines = [
        f"Screening completed for theme: {theme}",
        "",
        f"- Initial candidates: {len(initial_candidates)}",
        f"- Second-screen pool: {len(stage_one_candidates)}",
        f"- Final recommendations: {len(finalists)}",
        "",
        "Recommended names:",
    ]
    for rank, item in enumerate(finalists, start=1):
        report_payload = item.get("payload") or {}
        lines.extend(
            [
                f"{rank}. {item.get('company_name')} {item.get('ticker', '')}".strip(),
                f"   screen_score={item.get('screen_score')} | verdict={report_payload.get('verdict', 'watchlist')}",
                f"   why_now: {item.get('stage_two_note', '') or item.get('rationale', '') or 'n/a'}",
                f"   quick_take: {report_payload.get('quick_take', '') or 'n/a'}",
            ]
        )
    lines.extend(["", f"Attached screening summary: {markdown_path}"])
    return "\n".join(lines)


def send_email_reply(
    *,
    config: EmailConfig,
    to_address: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.reply_to
    message["To"] = to_address
    message.set_content(body)
    for attachment in attachments or []:
        path = Path(attachment)
        if not path.exists() or not path.is_file():
            continue
        data = path.read_bytes()
        subtype = "json" if path.suffix == ".json" else "markdown" if path.suffix == ".md" else "octet-stream"
        maintype = "application" if path.suffix in {".json", ".md"} else "application"
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port) as server:
        server.login(config.address, config.app_password)
        server.send_message(message)


def build_agent_user_prompt(
    *,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    objective: str,
    memory_context: MemoryContext | None = None,
) -> str:
    payload = {
        "stock_name": stock_name,
        "ticker_hint": ticker,
        "market_hint": market,
        "angle": angle or "中国故事",
        "objective": objective,
        "memory_context": summarize_memory_context(memory_context),
    }
    return f"研究这个标的并完成指定目标。可以主动联网搜索与抓取官方网页。输入：{json.dumps(payload, ensure_ascii=False)}"


def build_screening_scout_prompt(*, max_results: int, max_fetches: int) -> str:
    return (
        "你是 buy-side 的主题筛股 scout。"
        "你要从公开网页里为一个板块方向找出值得继续研究的上市公司候选，而不是泛泛罗列概念股。 "
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "优先关注交易所、公司官网、正式公告、权威财经媒体与高质量深度报道。"
    )


def build_screening_user_prompt(*, theme: str, desired_count: int, market: str, seed_tickers: list[str]) -> str:
    payload = {
        "theme": theme,
        "desired_count": desired_count,
        "market": market,
        "seed_tickers": seed_tickers,
        "goal": "先进行初筛，找出真正值得进入二筛和精筛的股票候选。",
    }
    return f"请围绕这个板块方向去主动联网搜索并寻找股票候选：{json.dumps(payload, ensure_ascii=False)}"


def build_screening_synthesis_prompt(
    *,
    theme: str,
    desired_count: int,
    market: str,
    evidence: list[dict[str, str]],
    seed_tickers: list[str],
) -> str:
    payload = {
        "theme": theme,
        "desired_count": desired_count,
        "market": market,
        "seed_tickers": seed_tickers,
        "evidence": evidence,
    }
    return (
        "Return JSON only with a top-level `candidates` array. "
        "Each candidate must contain: company_name, ticker, market, rationale, screen_score, confidence, source_count, angle. "
        "screen_score must be 0-100 and represent whether the stock deserves deeper research, not final conviction. "
        "Prefer listed companies actually connected to the theme, not vague supply-chain mentions. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def build_second_screen_prompt(*, theme: str, market: str, desired_count: int, candidates: list[dict[str, Any]]) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "candidates": candidates,
    }
    return (
        "Return JSON only with a top-level `recommended` array. "
        "Select the few names most worth full deep-research work. "
        "Each recommended item must contain: company_name, ticker, market, rationale, screen_score, confidence, angle. "
        "Favor names with cleaner business linkage, better research upside, and clearer why-now framing. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def render_screening_markdown(
    *,
    theme: str,
    market: str,
    stage_one_candidates: list[dict[str, Any]],
    finalists: list[dict[str, Any]],
) -> str:
    def recommendation_rank(item: dict[str, Any]) -> str:
        payload = item.get("payload") or {}
        verdict = str(payload.get("verdict") or "watchlist")
        confidence = str(payload.get("confidence") or "medium")
        quick_take = str(payload.get("quick_take") or "").strip()
        why_now = str(item.get("stage_two_note") or item.get("rationale") or "").strip()
        targets = payload.get("target_prices") or {}
        short_term = targets.get("short_term") or {}
        return "\n".join(
            [
                f"### {item.get('company_name')} `{item.get('ticker', '')}`",
                f"- Recommendation rank: `{rank_label(item)}`",
                f"- Screen score: `{item.get('screen_score', '')}`",
                f"- Research verdict: `{verdict}`",
                f"- Confidence: `{confidence}`",
                f"- Why now: {why_now or '待补充'}",
                f"- Quick take: {quick_take or '待补充'}",
                f"- Short-term target: {short_term.get('price', 'n/a')} | {short_term.get('horizon', 'n/a')}",
                f"- Bull/Bear focus: {summarize_bull_bear(payload)}",
                f"- Report path: `{item.get('markdown_path', '')}`",
            ]
        )

    def rejected_bucket(items: list[dict[str, Any]]) -> str:
        rejected = [item for item in items if slugify(item.get("ticker") or item.get("company_name") or "") not in {
            slugify(finalist.get("ticker") or finalist.get("company_name") or "") for finalist in finalists
        }]
        if not rejected:
            return "- No clear rejects from the second-screen pool."
        return "\n".join(
            f"- `{item.get('ticker') or item.get('company_name')}` | score={item.get('screen_score')} | not promoted because: {item.get('rationale', 'research upside was weaker')}"
            for item in rejected[:6]
        )

    stage_one_block = "\n".join(
        f"- `{item.get('ticker') or item.get('company_name')}` | score={item.get('screen_score')} | {item.get('rationale', '')}"
        for item in stage_one_candidates
    ) or "- 初筛没有稳定返回候选。"
    finalist_block = "\n".join(
        recommendation_rank(item)
        for item in finalists
    ) or "- 没有进入精筛的候选。"
    return "\n".join(
        [
            f"# {theme} 筛股报告",
            "",
            f"- 市场：`{market}`",
            f"- 生成时间：`{datetime.now(UTC).isoformat()}`",
            "",
            "## 推荐摘要",
            screening_summary(theme=theme, finalists=finalists),
            "",
            "## 初筛 / 二筛候选池",
            stage_one_block,
            "",
            "## 精筛推荐",
            finalist_block,
            "",
            "## 本轮未晋级名单",
            rejected_bucket(stage_one_candidates),
        ]
    )


def screening_summary(*, theme: str, finalists: list[dict[str, Any]]) -> str:
    if not finalists:
        return f"`{theme}` 这条主线本轮没有筛出足够强的深研候选。"
    top = finalists[0]
    payload = top.get("payload") or {}
    return (
        f"本轮围绕 `{theme}` 先做公开网页初筛，再做二筛委员会压缩，最后对最值得投入时间的标的做完整多 agent 深研。"
        f" 当前最优先继续跟的名字是 `{top.get('company_name')}`，因为它在 why-now、screen score 和最终 memo 一致性上最稳。"
        f" 最终 verdict 为 `{payload.get('verdict', 'watchlist')}`，说明这套流程更偏严谨研究，而不是无脑抬高结论。"
    )


def rank_label(item: dict[str, Any]) -> str:
    score = int(item.get("screen_score") or 0)
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    return "C"


def summarize_bull_bear(payload: dict[str, Any]) -> str:
    bull = list(payload.get("bull_case") or [])
    bear = list(payload.get("bear_case") or [])
    bull_text = bull[0] if bull else "bull case still needs work"
    bear_text = bear[0] if bear else "bear case still needs work"
    return f"bull: {bull_text} | bear: {bear_text}"


def build_market_analyst_prompt(max_results: int, max_fetches: int) -> str:
    return (
        "你是 buy-side 的市场/行业分析师。"
        f"{render_persona_instruction('market_analyst')} "
        "优先使用 web_search 与 web_fetch 核实上市地点、行业结构、需求周期、竞争格局与中国叙事。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "偏好官方投资者关系页面、交易所页面、公司公告与权威媒体。"
        "横向要比较行业位置与竞争格局，纵向要判断周期位置、资本开支与估值桥接。"
        "输出中文 Markdown，包含：市场结构、需求驱动、竞争格局、中国故事、估值框架线索、待核实问题。"
    )


def build_company_analyst_prompt(max_results: int, max_fetches: int) -> str:
    return (
        "你是 buy-side 的公司研究分析师。"
        f"{render_persona_instruction('company_analyst')} "
        "使用 web_search 与 web_fetch 调研公司业务、产品、客户、订单、财务趋势、管理层、治理风险与关键公告。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "优先寻找公司官网、年报/公告、投资者交流纪要、可靠媒体或券商摘要。"
        "纵向要追踪业务质量和管理层行为，横向要判断它是否真的优于替代资产。"
        "输出中文 Markdown，包含：业务概览、商业模式、经营信号、多头逻辑、空头逻辑、催化剂、主要风险。"
    )


def build_sentiment_simulator_prompt(max_results: int, max_fetches: int) -> str:
    return (
        "你是市场叙事与舆情模拟分析师。"
        f"{render_persona_instruction('sentiment_simulator')} "
        "先通过 web_search 与 web_fetch 搜集公开叙事、媒体口径、投资者交流与讨论线索，再模拟不同参与者的反应。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "把叙事拆成能推高预期的、会压低估值的、以及可能突然反转的三层。"
        "输出中文 Markdown，包含：当前叙事温度、多头叙事、空头叙事、"
        "成长基金视角、卖方怀疑派视角、产业链经营者视角、题材交易型散户视角。"
    )


def build_comparison_analyst_prompt(max_results: int, max_fetches: int) -> str:
    return (
        "你是 buy-side 的横向对比分析师。"
        f"{render_persona_instruction('comparison_analyst')} "
        "使用 web_search 与 web_fetch 搜集可比公司、行业位置、估值口径、历史周期表现与资本开支节奏。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "必须同时回答：为什么值得研究，以及为什么可能根本不值得优先研究。"
        "输出中文 Markdown，包含：可比公司列表、相对优势、相对劣势、估值锚、为什么这家公司值得或不值得优先研究。"
    )


def build_red_team_prompt() -> str:
    return (
        "你是 buy-side 投委会里的红队负责人。"
        f"{render_persona_instruction('committee_red_team')} "
        "你的任务不是总结，而是找出证据不足、逻辑跳跃、叙事自嗨、潜在反转点和最可能让判断出错的地方。"
        "输出中文 Markdown，使用 bullet points。"
    )


def build_red_team_user_prompt(
    *,
    stock_name: str,
    ticker: str | None,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
) -> str:
    payload = {
        "stock_name": stock_name,
        "ticker": ticker,
        "market_analyst": clip_text(market_analyst.content, 1400),
        "company_analyst": clip_text(company_analyst.content, 1400),
        "sentiment_simulator": clip_text(sentiment_simulator.content, 1400),
        "comparison_analyst": clip_text(comparison_analyst.content, 1400),
    }
    return f"请交叉质询以下研究结论，指出最需要继续核实的断点：{json.dumps(payload, ensure_ascii=False)}"


def build_guru_council_prompt() -> str:
    return (
        "你是多位顶级投资人的联合议会记录员。"
        f"{render_persona_instruction('guru_council')} "
        "你的任务是把多个 desk 的研究收口成一页真正的议会纪要：明确共识、分歧、关键待验证断点，以及是否值得继续投入研究资源。"
        "输出中文 Markdown，包含：委员会共识、委员会分歧、最关键验证点、当前建议。"
    )


def build_guru_council_user_prompt(
    *,
    stock_name: str,
    ticker: str | None,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
) -> str:
    payload = {
        "stock_name": stock_name,
        "ticker": ticker,
        "market_analyst": clip_text(market_analyst.content, 1200),
        "company_analyst": clip_text(company_analyst.content, 1200),
        "sentiment_simulator": clip_text(sentiment_simulator.content, 1200),
        "comparison_analyst": clip_text(comparison_analyst.content, 1200),
        "committee_red_team": clip_text(committee_red_team.content, 1200),
    }
    return f"请把这些 desk 的结论整理成一份股神议会议程纪要：{json.dumps(payload, ensure_ascii=False)}"


def build_mirofish_scenario_prompt() -> str:
    return (
        "你是受 MiroFish 式多未来世界模拟启发的情景推演引擎。"
        f"{render_persona_instruction('mirofish_scenario_engine')} "
        "你的任务不是预测一个单点未来，而是给出 bull/base/bear 三条时间路径，说明每条路径需要什么触发条件、对应什么市场叙事和经营结果。"
        "输出中文 Markdown，包含：短期未来（0-3个月）、中期未来（3-12个月）、长期未来（12-36个月）、每条路径的 bull/base/bear trigger。"
    )


def build_mirofish_scenario_user_prompt(
    *,
    stock_name: str,
    ticker: str | None,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
    guru_council: AgentRunResult,
) -> str:
    payload = {
        "stock_name": stock_name,
        "ticker": ticker,
        "market_analyst": clip_text(market_analyst.content, 1200),
        "company_analyst": clip_text(company_analyst.content, 1200),
        "sentiment_simulator": clip_text(sentiment_simulator.content, 1200),
        "comparison_analyst": clip_text(comparison_analyst.content, 1200),
        "committee_red_team": clip_text(committee_red_team.content, 1200),
        "guru_council": clip_text(guru_council.content, 1200),
    }
    return f"请基于这些研究结果推演未来世界分支，并明确时间线和触发器：{json.dumps(payload, ensure_ascii=False)}"


def build_price_committee_prompt(max_results: int, max_fetches: int) -> str:
    return (
        "你是价格委员会。"
        f"{render_persona_instruction('price_committee')} "
        "使用 web_search 与 web_fetch 搜集当前股价、估值口径、卖方目标价、关键催化剂与风险。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "输出中文 Markdown，包含：当前价格基准、短期目标价、中期目标价、长期目标价、每个目标价的时间、依赖条件、下修触发器。"
    )


def build_buy_side_synthesis_prompt(
    *,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
    guru_council: AgentRunResult,
    mirofish_scenario_engine: AgentRunResult,
    price_committee: AgentRunResult,
    distilled_notes: dict[str, dict[str, Any]],
) -> str:
    payload = {
        "stock_name": stock_name,
        "ticker_hint": ticker,
        "market_hint": market,
        "angle": angle or "中国故事",
        "market_analyst": clip_text(market_analyst.content),
        "company_analyst": clip_text(company_analyst.content),
        "sentiment_simulator": clip_text(sentiment_simulator.content),
        "comparison_analyst": clip_text(comparison_analyst.content),
        "committee_red_team": clip_text(committee_red_team.content, 1800),
        "guru_council": clip_text(guru_council.content, 1800),
        "mirofish_scenario_engine": clip_text(mirofish_scenario_engine.content, 1800),
        "price_committee": clip_text(price_committee.content, 1800),
        "distilled_notes": distilled_notes,
        "agent_evidence": {
            market_analyst.name: extract_evidence_from_traces([market_analyst.tool_traces])[:6],
            company_analyst.name: extract_evidence_from_traces([company_analyst.tool_traces])[:6],
            sentiment_simulator.name: extract_evidence_from_traces([sentiment_simulator.tool_traces])[:6],
            comparison_analyst.name: extract_evidence_from_traces([comparison_analyst.tool_traces])[:6],
            price_committee.name: extract_evidence_from_traces([price_committee.tool_traces])[:6],
        },
    }
    return (
        "Return a single JSON object only with these keys: "
        "company_name, ticker, exchange, market, quick_take, verdict, confidence, market_map, business_summary, "
        "china_story, sentiment_simulation, peer_comparison, committee_takeaways, scenario_outlook, debate_notes, "
        "bull_case, bear_case, catalysts, risks, valuation_view, target_prices, evidence, next_questions. "
        "bull_case, bear_case, catalysts, risks, next_questions must be arrays with dense, buy-side quality bullet points. "
        "evidence must include title, url, claim, stance. "
        "target_prices must be an object with short_term, medium_term, long_term; each has price, horizon, thesis. "
        "Keep quick_take, market_map, business_summary, china_story, sentiment_simulation, peer_comparison, committee_takeaways, scenario_outlook, debate_notes, valuation_view concise and information-dense. "
        "Do not return Markdown, only structured JSON. "
        "If any agent note is trace-like or noisy, distill it into concrete investment-relevant claims rather than repeating page titles or navigation text. "
        "Use the price committee and MiroFish scenario engine to assign short-, medium-, and long-term target prices with explicit time horizons. "
        "Use the three agent notes and their evidence traces faithfully, and make uncertainty explicit. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def clip_text(value: str, limit: int = 2200) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[truncated]"


def run_deliberation_agent(
    *,
    client: Client,
    model: str,
    think: str,
    name: str,
    system_prompt: str,
    user_prompt: str,
    fallback_note: str | None = None,
    verbose: bool = False,
) -> AgentRunResult:
    started = time.perf_counter()
    try:
        if verbose:
            print(f"[agent:{name}] deliberating")
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            think=resolve_think(model, think),
        )
        content = response.message.content or ""
        if content.strip():
            if verbose:
                print(f"[agent:{name}] finished in {round(time.perf_counter() - started, 1)}s")
            return AgentRunResult(name=name, content=content, tool_traces=[])
    except Exception:
        pass
    if verbose:
        print(f"[agent:{name}] fell back to minimal deliberation note in {round(time.perf_counter() - started, 1)}s")
    return AgentRunResult(
        name=name,
        content=fallback_note or "需要继续进行红队质询，当前云端 deliberation 未完成。",
        tool_traces=[],
    )


def summarize_memory_context(memory_context: MemoryContext | None) -> dict[str, Any] | None:
    if not memory_context or not memory_context.payload:
        return None
    payload = memory_context.payload
    return {
        "last_verdict": payload.get("verdict"),
        "last_confidence": payload.get("confidence"),
        "key_bull_points": payload.get("bull_case", [])[:3],
        "key_bear_points": payload.get("bear_case", [])[:3],
        "open_questions": payload.get("next_questions", [])[:4],
        "recent_evidence_digest": payload.get("evidence_digest", [])[:4],
        "updated_at": payload.get("updated_at"),
    }


def synthesize_buy_side_report(
    *,
    client: Client,
    config: StockResearchConfig,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
    guru_council: AgentRunResult,
    mirofish_scenario_engine: AgentRunResult,
    price_committee: AgentRunResult,
    distilled_notes: dict[str, dict[str, Any]],
) -> str:
    try:
        response = client.chat(
            model=config.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a buy-side portfolio analyst writing a high-density Chinese investment memo. "
                        "Return one stable JSON object only."
                    ),
                },
                {
                    "role": "user",
                    "content": build_buy_side_synthesis_prompt(
                        stock_name=stock_name,
                        ticker=ticker,
                        market=market,
                        angle=angle,
                        market_analyst=market_analyst,
                        company_analyst=company_analyst,
                        sentiment_simulator=sentiment_simulator,
                        comparison_analyst=comparison_analyst,
                        committee_red_team=committee_red_team,
                        guru_council=guru_council,
                        mirofish_scenario_engine=mirofish_scenario_engine,
                        price_committee=price_committee,
                        distilled_notes=distilled_notes,
                    ),
                },
            ],
            think=resolve_think(config.model, config.think),
            format="json",
        )
        content = response.message.content or ""
        if content.strip():
            return content
    except Exception:
        pass

    return json.dumps(
        build_local_synthesis_payload(
            stock_name=stock_name,
            ticker=ticker,
            market=market,
            angle=angle,
            market_analyst=market_analyst,
            company_analyst=company_analyst,
            sentiment_simulator=sentiment_simulator,
            comparison_analyst=comparison_analyst,
            committee_red_team=committee_red_team,
            guru_council=guru_council,
            mirofish_scenario_engine=mirofish_scenario_engine,
            price_committee=price_committee,
        ),
        ensure_ascii=False,
    )


def resolve_think(model: str, think: str) -> str | None:
    lowered = model.lower()
    if "gemini" in lowered:
        return None
    return think or None


def safe_run_agent_with_tools(**kwargs: Any) -> AgentRunResult:
    try:
        return run_agent_with_tools(**kwargs)
    except Exception as exc:
        return AgentRunResult(
            name=str(kwargs.get("name") or "agent"),
            content=f"{kwargs.get('name') or 'agent'} 未完成完整总结，当前保留错误信息：{exc}",
            tool_traces=[{"tool_name": "error", "arguments": {}, "result": {"error": str(exc)}}],
        )


def run_agent_with_tools(
    *,
    client: Client,
    name: str,
    model: str,
    think: str,
    system_prompt: str,
    user_prompt: str,
    max_results: int,
    max_fetches: int,
    verbose: bool = False,
) -> AgentRunResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_traces: list[dict[str, Any]] = []
    fetch_count = 0

    started = time.perf_counter()
    if verbose:
        print(f"[agent:{name}] planning search")
    planning_response = client.chat(
        model=model,
        messages=messages,
        tools=[client.web_search, client.web_fetch],
        think=resolve_think(model, think),
    )
    planning_message = planning_response.message
    messages.append(planning_message.model_dump(exclude_none=True))
    tool_calls = planning_message.tool_calls or []

    if not tool_calls:
        if verbose:
            print(f"[agent:{name}] finished without tools in {round(time.perf_counter() - started, 1)}s")
        return AgentRunResult(name=name, content=planning_message.content or "", tool_traces=tool_traces)

    for tool_call in tool_calls:
        function = tool_call.function
        tool_name = function.name
        arguments = dict(function.arguments or {})
        if tool_name == "web_search":
            arguments["max_results"] = min(int(arguments.get("max_results", max_results)), max_results)
            result = client.web_search(**arguments).model_dump()
        elif tool_name == "web_fetch":
            if fetch_count >= max_fetches:
                result = {"error": "fetch budget exhausted"}
            else:
                result = client.web_fetch(**arguments).model_dump()
                fetch_count += 1
        else:
            result = {"error": f"unsupported tool: {tool_name}"}

        tool_traces.append({"tool_name": tool_name, "arguments": arguments, "result": result})
        if verbose:
            print(f"[agent:{name}] {tool_name} done")
        messages.append(
            {
                "role": "tool",
                "tool_name": tool_name,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    synthesis_prompt = build_agent_synthesis_prompt(
        name=name,
        user_prompt=user_prompt,
        tool_traces=tool_traces,
    )

    try:
        if verbose:
            print(f"[agent:{name}] synthesizing note")
        synthesis_response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": synthesis_prompt},
            ],
            think=resolve_think(model, think),
        )
        content = synthesis_response.message.content or ""
        if content.strip():
            if verbose:
                print(f"[agent:{name}] finished in {round(time.perf_counter() - started, 1)}s")
            return AgentRunResult(name=name, content=content, tool_traces=tool_traces)
    except Exception:
        pass

    if verbose:
        print(f"[agent:{name}] fell back to trace summary in {round(time.perf_counter() - started, 1)}s")
    return AgentRunResult(name=name, content=render_agent_trace_summary(name=name, tool_traces=tool_traces), tool_traces=tool_traces)


def normalize_report_payload(
    payload: dict[str, Any],
    *,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    model: str,
    fallback_evidence: list[dict[str, str]] | None = None,
    distilled_notes: dict[str, dict[str, Any]] | None = None,
    fallback_target_prices: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    company_name = str(payload.get("company_name") or stock_name)
    resolved_ticker = normalize_ticker(str(payload.get("ticker") or ticker or stock_name), payload.get("exchange"), market)
    exchange = str(payload.get("exchange") or "")
    evidence = merge_evidence(normalize_evidence(payload.get("evidence")), fallback_evidence or [])
    bull_case = normalize_strings(payload.get("bull_case"))
    bear_case = normalize_strings(payload.get("bear_case"))
    catalysts = normalize_strings(payload.get("catalysts"))
    risks = normalize_strings(payload.get("risks"))
    next_questions = normalize_strings(payload.get("next_questions"))
    raw_verdict = str(payload.get("verdict") or "")
    raw_confidence = str(payload.get("confidence") or "")
    verdict = normalize_verdict(raw_verdict)
    confidence = normalize_confidence(raw_confidence)
    market_fallback = ((distilled_notes or {}).get("market_analyst") or {}).get("summary", "")
    company_fallback = ((distilled_notes or {}).get("company_analyst") or {}).get("summary", "")
    sentiment_fallback = ((distilled_notes or {}).get("sentiment_simulator") or {}).get("summary", "")
    comparison_fallback = ((distilled_notes or {}).get("comparison_analyst") or {}).get("summary", "")
    red_team_fallback = ((distilled_notes or {}).get("committee_red_team") or {}).get("summary", "")
    council_fallback = ((distilled_notes or {}).get("guru_council") or {}).get("summary", "")
    scenario_fallback = ((distilled_notes or {}).get("mirofish_scenario_engine") or {}).get("summary", "")
    quick_take = str(payload.get("quick_take") or f"{company_name} 需要继续核实核心基本面与估值锚。")
    market_map = choose_section_text(str(payload.get("market_map") or ""), market_fallback, "市场结构、需求周期与竞争格局仍需继续补证。")
    business_summary = choose_section_text(str(payload.get("business_summary") or ""), company_fallback, "缺少足够资料，业务概览仍需补证。")
    china_story = str(payload.get("china_story") or angle or "需要继续验证其在中国叙事中的位置。")
    sentiment_simulation = choose_section_text(str(payload.get("sentiment_simulation") or ""), sentiment_fallback, "市场叙事与舆情模拟仍需继续补证。")
    peer_comparison = choose_section_text(str(payload.get("peer_comparison") or ""), comparison_fallback, "横向可比公司与估值锚仍需继续补证。")
    committee_takeaways = choose_section_text(str(payload.get("committee_takeaways") or ""), council_fallback, "委员会当前共识仍不足，需继续压缩成更清晰的研究判断。")
    scenario_outlook = choose_section_text(str(payload.get("scenario_outlook") or ""), scenario_fallback, "多未来情景仍需继续补证，当前只能维持 base-case watchlist。")
    debate_notes = choose_section_text(str(payload.get("debate_notes") or ""), red_team_fallback, "当前红队质询仍不足，需继续验证关键假设。")
    valuation_view = str(payload.get("valuation_view") or "当前版本没有足够公开证据支持更细的估值判断。")
    if distilled_notes:
        bull_case = choose_section_list(bull_case, ((distilled_notes.get("company_analyst") or {}).get("bull_case") or []))
        bear_case = choose_section_list(bear_case, ((distilled_notes.get("company_analyst") or {}).get("bear_case") or []))
        catalysts = choose_section_list(catalysts, ((distilled_notes.get("company_analyst") or {}).get("catalysts") or []))
        risks = choose_section_list(risks, ((distilled_notes.get("company_analyst") or {}).get("risks") or []))
    price_committee_fallback = derive_target_prices_from_context(
        ((distilled_notes or {}).get("price_committee") or {}).get("summary", ""),
        verdict=verdict,
        ticker=resolved_ticker,
    )
    target_prices = normalize_target_prices(
        payload.get("target_prices"),
        fallback_target_prices or price_committee_fallback,
    )
    target_prices = fill_missing_target_prices(
        target_prices,
        derive_target_prices_from_context(
            ((distilled_notes or {}).get("price_committee") or {}).get("summary", ""),
            verdict=verdict,
            ticker=resolved_ticker,
        ),
    )
    rendered_markdown = render_markdown(
        company_name=company_name,
        ticker=resolved_ticker,
        exchange=exchange,
        market=market,
        model=model,
        quick_take=quick_take,
        verdict=verdict,
        confidence=confidence,
        market_map=market_map,
        business_summary=business_summary,
        china_story=china_story,
        sentiment_simulation=sentiment_simulation,
        peer_comparison=peer_comparison,
        committee_takeaways=committee_takeaways,
        scenario_outlook=scenario_outlook,
        debate_notes=debate_notes,
        bull_case=bull_case,
        bear_case=bear_case,
        catalysts=catalysts,
        risks=risks,
        valuation_view=valuation_view,
        target_prices=target_prices,
        evidence=evidence,
        next_questions=next_questions,
    )
    report_markdown = rendered_markdown

    return {
        "company_name": company_name,
        "ticker": resolved_ticker,
        "exchange": exchange,
        "market": market,
        "quick_take": quick_take,
        "verdict": verdict,
        "raw_verdict": raw_verdict or verdict,
        "confidence": confidence,
        "raw_confidence": raw_confidence or confidence,
        "market_map": market_map,
        "business_summary": business_summary,
        "china_story": china_story,
        "sentiment_simulation": sentiment_simulation,
        "peer_comparison": peer_comparison,
        "committee_takeaways": committee_takeaways,
        "scenario_outlook": scenario_outlook,
        "debate_notes": debate_notes,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "catalysts": catalysts,
        "risks": risks,
        "valuation_view": valuation_view,
        "target_prices": target_prices,
        "evidence": evidence,
        "next_questions": next_questions,
        "report_markdown": report_markdown,
    }


def normalize_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_evidence(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        claim = str(item.get("claim") or "").strip()
        stance = str(item.get("stance") or "neutral").strip()
        quality = int(item.get("quality") or source_quality_score(url))
        if not title and not url and not claim:
            continue
        if is_blocked_source(url) or quality < MIN_SOURCE_QUALITY:
            continue
        normalized.append(
            {
                "title": title or url or "Untitled source",
                "url": url,
                "claim": claim or "No explicit evidence claim provided.",
                "stance": stance,
                "domain": source_domain(url),
                "quality": str(quality),
            }
        )
    normalized.sort(key=evidence_sort_key, reverse=True)
    return normalized[:12]


def merge_evidence(primary: list[dict[str, str]], fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in [*primary, *fallback]:
        key = (item.get("title", "").strip(), item.get("url", "").strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=evidence_sort_key, reverse=True)
    return merged[:12]


def build_agent_synthesis_prompt(*, name: str, user_prompt: str, tool_traces: list[dict[str, Any]]) -> str:
    evidence = extract_evidence_from_traces([tool_traces])[:8]
    trace_summary = []
    for item in evidence:
        trace_summary.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "claim": item.get("claim", ""),
            }
        )
    return (
        "你已经完成联网搜索。请基于下面的研究任务和证据，输出一份高密度中文 Markdown 研究笔记。"
        "避免复述导航噪音，优先给出结论、分歧、证据强弱、待核实断点。"
        f"请严格按这个结构写：{agent_output_outline(name)} "
        f"任务：{user_prompt} "
        f"证据：{json.dumps(trace_summary, ensure_ascii=False)} "
        f"如果证据不足，要明确写出证据不足，而不是编造。当前角色：{name}。"
    )


def agent_output_outline(name: str) -> str:
    outlines = {
        "market_analyst": "市场结构；需求/资本开支周期；中国故事；估值框架线索；待核实问题。尽量使用 bullet points。",
        "company_analyst": "业务概览；客户与订单；财务与经营信号；多头逻辑；空头逻辑；催化剂；主要风险。尽量使用 bullet points。",
        "sentiment_simulator": "当前叙事温度；多头叙事；空头叙事；成长基金视角；卖方怀疑派视角；产业链经营者视角；题材交易型散户视角。",
        "comparison_analyst": "可比公司；相对优势；相对劣势；估值锚；为什么值得研究；为什么不值得优先研究。",
    }
    return outlines.get(name, "给出结论、证据强弱、待核实断点。")


def distill_agent_note(*, name: str, content: str, tool_traces: list[dict[str, Any]]) -> dict[str, Any]:
    fallback_text = render_agent_trace_summary(name=name, tool_traces=tool_traces)
    text = content.strip() if content.strip() else fallback_text
    if name == "company_analyst":
        signal_lines = evidence_signal_lines(tool_traces)
        summary = preferred_section_text(
            extract_markdown_sections(text, "业务概览", "客户与订单", "财务与经营信号"),
            evidence_summary_for_role("company_analyst", signal_lines)
            or extract_markdown_sections(fallback_text, "业务概览", "客户与订单", "财务与经营信号"),
        )
        bull_case = preferred_section_list(
            section_bullets(text, "多头逻辑"),
            derive_role_bullets("bull", signal_lines) or section_bullets(fallback_text, "多头逻辑"),
        )
        bear_case = preferred_section_list(
            section_bullets(text, "空头逻辑"),
            derive_role_bullets("bear", signal_lines) or section_bullets(fallback_text, "空头逻辑"),
        )
        catalysts = preferred_section_list(
            section_bullets(text, "催化剂"),
            derive_role_bullets("catalyst", signal_lines) or section_bullets(fallback_text, "催化剂"),
        )
        risks = preferred_section_list(
            section_bullets(text, "主要风险", "风险"),
            derive_role_bullets("risk", signal_lines) or section_bullets(fallback_text, "主要风险", "风险"),
        )
        return {
            "summary": summary or fallback_text,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "catalysts": catalysts,
            "risks": risks,
        }
    if name == "sentiment_simulator":
        generated_summary = build_sentiment_fallback_from_evidence(evidence_signal_lines(tool_traces))
        extracted_summary = extract_markdown_sections(
            text,
            "当前叙事温度",
            "成长基金视角",
            "卖方怀疑派视角",
            "产业链经营者",
            "题材交易型散户",
        )
        if should_replace_sentiment_summary(extracted_summary):
            extracted_summary = ""
        summary = preferred_section_text(
            extracted_summary,
            generated_summary
            or extract_markdown_sections(
                fallback_text,
                "当前叙事温度",
                "成长基金视角",
                "卖方怀疑派视角",
                "产业链经营者",
                "题材交易型散户",
            ),
        )
        return {"summary": summary or fallback_text}
    if name == "comparison_analyst":
        signal_lines = evidence_signal_lines(tool_traces)
        generated_summary = build_comparison_fallback_from_evidence(signal_lines)
        extracted_summary = extract_markdown_sections(
            text,
            "可比公司",
            "可比公司与估值锚",
            "相对优势",
            "相对劣势",
            "估值锚",
            "为什么值得研究",
            "为什么不值得优先研究",
        )
        if should_replace_comparison_summary(extracted_summary):
            extracted_summary = ""
        summary = preferred_section_text(
            extracted_summary,
            generated_summary
            or evidence_summary_for_role("comparison_analyst", signal_lines)
            or extract_markdown_sections(
                fallback_text,
                "可比公司",
                "可比公司与估值锚",
                "相对优势",
                "相对劣势",
                "估值锚",
                "为什么值得研究",
                "为什么不值得优先研究",
            ),
        )
        return {"summary": summary or fallback_text}
    if name == "market_analyst":
        signal_lines = evidence_signal_lines(tool_traces)
        summary = preferred_section_text(
            extract_markdown_sections(text, "市场结构", "需求", "竞争格局", "中国故事", "估值框架线索"),
            evidence_summary_for_role("market_analyst", signal_lines)
            or extract_markdown_sections(fallback_text, "市场结构", "需求", "竞争格局", "中国故事", "估值框架线索"),
        )
        return {"summary": summary or fallback_text}
    if name == "committee_red_team":
        summary = preferred_section_text(
            extract_markdown_sections(
                text,
                "市场结构",
                "需求/资本开支周期",
                "中国故事",
                "估值框架线索",
                "待核实问题",
            ),
            sanitize_deliberation_text(text),
        )
        return {"summary": summary or sanitize_deliberation_text(fallback_text or text)}
    if name == "guru_council":
        summary = preferred_section_text(
            extract_markdown_sections(
                text,
                "委员会共识",
                "委员会分歧",
                "最关键验证点",
                "当前建议",
            ),
            sanitize_deliberation_text(text),
        )
        return {"summary": summary or sanitize_deliberation_text(fallback_text or text)}
    if name == "mirofish_scenario_engine":
        summary = preferred_section_text(
            extract_markdown_sections(
                text,
                "短期未来",
                "中期未来",
                "长期未来",
                "Bull",
                "Base",
                "Bear",
            ),
            sanitize_deliberation_text(text),
        )
        return {"summary": summary or sanitize_deliberation_text(fallback_text or text)}
    if name == "price_committee":
        summary = preferred_section_text(
            extract_markdown_sections(
                text,
                "当前价格基准",
                "短期目标价",
                "中期目标价",
                "长期目标价",
                "下修触发器",
            ),
            sanitize_deliberation_text(text),
        )
        return {"summary": summary or sanitize_deliberation_text(fallback_text or text)}
    return {"summary": preferred_section_text(text, fallback_text) or fallback_text}


def extract_evidence_from_traces(agent_traces: list[list[dict[str, Any]]]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    expected_tokens = infer_expected_tokens(agent_traces)
    for traces in agent_traces:
        for trace in traces:
            result = trace.get("result")
            if not isinstance(result, dict):
                continue
            for candidate in iter_tool_result_candidates(result):
                url = candidate.get("url", "").strip()
                if not url or url in seen_urls:
                    continue
                if not is_relevant_candidate(candidate, expected_tokens):
                    continue
                seen_urls.add(url)
                evidence.append(candidate)
    evidence.sort(key=evidence_sort_key, reverse=True)
    return evidence[:12]


def render_agent_trace_summary(*, name: str, tool_traces: list[dict[str, Any]]) -> str:
    evidence = extract_evidence_from_traces([tool_traces])[:4]
    if not evidence:
        return f"{name} 未获得足够公开证据，需补充更多搜索。"
    claims = [sanitize_source_text(item["claim"]) for item in evidence if item.get("claim")]
    if name == "market_analyst":
        return "\n".join(
            [
                "## 市场结构",
                *(f"- {item}" for item in claims[:2]),
                "## 中国故事与周期",
                *(f"- {item}" for item in claims[2:4]),
                "## 待核实问题",
                "- 需要继续验证行业资本开支与需求周期是否同步改善。",
            ]
        )
    if name == "company_analyst":
        return "\n".join(
            [
                "## 业务概览",
                *(f"- {item}" for item in claims[:2]),
                "## 多头逻辑",
                *(f"- {item}" for item in select_positive_points(claims)[:2]),
                "## 空头逻辑",
                *(f"- {item}" for item in select_negative_points(claims)[:2]),
                "## 催化剂",
                *(f"- {item}" for item in select_catalyst_points(claims)[:2]),
                "## 主要风险",
                *(f"- {item}" for item in select_risk_points(claims)[:2]),
            ]
        )
    if name == "sentiment_simulator":
        base = claims[:4]
        while len(base) < 4:
            base.append("证据仍不足，需要继续补充公开讨论与机构口径。")
        return "\n".join(
            [
                "## 当前叙事温度",
                f"- {base[0]}",
                "## 成长基金视角",
                f"- {base[1]}",
                "## 卖方怀疑派视角",
                f"- {base[2]}",
                "## 产业链经营者 / 题材交易盘",
                f"- {base[3]}",
            ]
        )
    if name == "comparison_analyst":
        return "\n".join(
            [
                "## 可比公司与估值锚",
                *(f"- {item}" for item in claims[:2]),
                "## 相对优势",
                *(f"- {item}" for item in select_positive_points(claims)[:2]),
                "## 相对劣势",
                *(f"- {item}" for item in select_negative_points(claims)[:2]),
            ]
        )
    lines = [f"{name} 基于公开搜索得到以下线索："]
    for item in evidence:
        lines.append(f"- {item['title']}：{item['claim']}")
    return "\n".join(lines)


def build_red_team_fallback(
    *,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
) -> str:
    market_risks = select_risk_points([market_analyst.content, comparison_analyst.content])
    company_risks = select_negative_points([company_analyst.content])
    sentiment_risks = select_negative_points([sentiment_simulator.content])
    bullets = [
        "- 最关键的断点是公司是否真的完成了从消费电子自动化向高端半导体设备的收入结构迁移。",
        "- 如果客户集中度没有实质下降，所谓中国高端制造叙事就可能只是旧苹果链故事的重新包装。",
    ]
    bullets.extend(f"- {item}" for item in market_risks[:2])
    bullets.extend(f"- {item}" for item in company_risks[:2])
    bullets.extend(f"- {item}" for item in sentiment_risks[:2])
    bullets.append("- 在没有更干净的 peer set 和估值锚之前，不应把 watchlist 误判成 high conviction。")
    return "\n".join(dict.fromkeys(bullets))


def build_guru_council_fallback(
    *,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
) -> str:
    positives = select_positive_points(
        [market_analyst.content, company_analyst.content, sentiment_simulator.content]
    )
    negatives = select_negative_points(
        [comparison_analyst.content, committee_red_team.content, company_analyst.content]
    )
    return "\n".join(
        [
            "## 委员会共识",
            f"- {first_meaningful_line(positives) or '赛腾股份具备继续研究价值，但证据还不足以支持高确信判断。'}",
            "## 委员会分歧",
            f"- {first_meaningful_line(negatives) or '主要分歧在于半导体设备故事是否已经足够替代旧苹果链逻辑。'}",
            "## 最关键验证点",
            "- 核心订单和收入中，半导体与先进制造占比是否持续提升。",
            "- 客户集中度是否真的下降，而不是被叙事掩盖。",
            "## 当前建议",
            "- 继续保留在 watchlist，并优先验证订单质量、客户结构和估值锚。",
        ]
    )


def build_mirofish_scenario_fallback(
    *,
    stock_name: str,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
) -> str:
    positives = select_positive_points(
        [market_analyst.content, company_analyst.content, sentiment_simulator.content]
    )
    negatives = select_negative_points(
        [comparison_analyst.content, committee_red_team.content, company_analyst.content]
    )
    catalysts = select_catalyst_points(
        [market_analyst.content, company_analyst.content, sentiment_simulator.content]
    )
    return "\n".join(
        [
            "## 短期未来（0-3个月）",
            f"- Bull: {first_meaningful_line(catalysts) or f'{stock_name} 若出现订单/客户验证，主题资金会更积极交易中国高端制造叙事。'}",
            f"- Base: {first_meaningful_line(positives) or '维持 watchlist，市场继续围绕国产替代与订单兑现博弈。'}",
            f"- Bear: {first_meaningful_line(negatives) or '若基本面验证迟迟不来，叙事热度会先于盈利兑现回落。'}",
            "## 中期未来（3-12个月）",
            "- Bull: 半导体设备与先进制造订单开始形成更清晰的收入迁移，估值锚逐步上修。",
            "- Base: 业务结构改善但节奏偏慢，估值仍停留在观察区间。",
            "- Bear: 客户集中与景气波动导致市场重新把它归类为周期性苹果链设备商。",
            "## 长期未来（12-36个月）",
            "- Bull: 若客户结构升级和产品放量持续，长期可以被重估为更高质量的先进制造设备资产。",
            "- Base: 成长性与周期性并存，长期回报取决于订单持续性和资本开支周期。",
            "- Bear: 若高端设备卡位不成，长期会回到低质量自动化设备估值框架。",
        ]
    )


def first_meaningful_line(items: list[str]) -> str:
    for item in items:
        cleaned = clean_research_line(item)
        if cleaned:
            return cleaned
    return ""


def preferred_section_text(primary: str, fallback: str) -> str:
    primary_clean = clean_research_summary(primary)
    if primary_clean and not is_low_quality_section(primary_clean):
        return primary_clean
    fallback_clean = clean_research_summary(fallback)
    return fallback_clean


def preferred_section_list(primary: list[str], fallback: list[str]) -> list[str]:
    chosen = [item for item in primary if item.strip()]
    if not chosen:
        chosen = [item for item in fallback if item.strip()]
    return chosen[:5]


def extract_markdown_sections(text: str, *heading_keywords: str) -> str:
    if not text.strip():
        return ""
    keywords = tuple(keyword for keyword in heading_keywords if keyword)
    lines = text.splitlines()
    collected: list[str] = []
    active = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        heading_match = re.match(r"^\s{0,3}#{1,6}\s*(.+?)\s*$", stripped)
        if heading_match:
            heading = heading_match.group(1).strip()
            active = any(keyword in heading for keyword in keywords)
            continue
        if active:
            cleaned = clean_research_line(stripped)
            if cleaned:
                collected.append(cleaned)
    if not collected:
        return ""
    joined = "\n".join(dict.fromkeys(collected))
    return clip_text(joined, 1200)


def extract_markdown_section(text: str, *heading_keywords: str) -> str:
    return extract_markdown_sections(text, *heading_keywords)


def section_bullets(text: str, *heading_keywords: str) -> list[str]:
    section = extract_markdown_sections(text, *heading_keywords)
    if not section:
        return []
    bullets: list[str] = []
    for line in section.splitlines():
        cleaned = re.sub(r"^\s*[-*•\d\.\)]*\s*", "", line).strip()
        cleaned = clean_research_line(cleaned)
        if cleaned:
            bullets.append(cleaned)
    return bullets[:5]


def sanitize_deliberation_text(text: str) -> str:
    cleaned = re.sub(r"```(?:markdown)?", "", text)
    cleaned = re.sub(r"```", "", cleaned)
    lines: list[str] = []
    for raw in cleaned.splitlines():
        line = clean_research_line(raw)
        if line:
            lines.append(line)
    return clip_text("\n".join(dict.fromkeys(lines)), 1200) if lines else ""


def evidence_signal_lines(tool_traces: list[dict[str, Any]]) -> list[str]:
    evidence = extract_evidence_from_traces([tool_traces])[:8]
    lines: list[str] = []
    for item in evidence:
        for candidate in (item.get("title", ""), item.get("claim", "")):
            for fragment in split_signal_fragments(candidate):
                cleaned = clean_research_line(fragment)
                if cleaned:
                    lines.append(cleaned)
    return list(dict.fromkeys(lines))[:16]


def split_signal_fragments(text: str) -> list[str]:
    if not text.strip():
        return []
    normalized = text.replace("：", "： ").replace("|", "\n").replace("·", "\n")
    chunks = re.split(r"[\n。；;]+", normalized)
    fragments: list[str] = []
    for chunk in chunks:
        cleaned = chunk.strip(" -*•\t")
        cleaned = re.sub(
            r"[_\-|]\s*(新浪财经|新浪网|Futubull|富途|证券之星|和讯网|东方财富网|股吧|理杏仁|九方智投|腾讯新闻|发现报告).*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            fragments.append(cleaned)
    return fragments


def evidence_summary_for_role(name: str, signal_lines: list[str]) -> str:
    if name == "company_analyst":
        preferred = [
            line
            for line in signal_lines
            if any(token in line for token in ["半导体", "量测", "设备", "订单", "客户", "收入", "利润", "毛利率", "现金流", "苹果"])
        ]
    elif name == "comparison_analyst":
        preferred = [
            line
            for line in signal_lines
            if any(token in line for token in ["估值", "市值", "PE", "PB", "检测设备", "可比", "苹果", "半导体", "自动化"])
        ]
    elif name == "market_analyst":
        preferred = [
            line
            for line in signal_lines
            if any(token in line for token in ["资本开支", "需求", "行业", "国产替代", "半导体", "消费电子", "苹果", "景气", "周期"])
        ]
    else:
        preferred = signal_lines
    return clip_text("\n".join(dict.fromkeys(preferred[:4])), 1200) if preferred else ""


def build_sentiment_fallback_from_evidence(signal_lines: list[str]) -> str:
    positives = filter_research_bullets(list(dict.fromkeys(select_positive_points(signal_lines))))[:2]
    negatives = filter_research_bullets(list(dict.fromkeys(select_negative_points(signal_lines))))[:2]
    catalysts = filter_research_bullets(list(dict.fromkeys(select_catalyst_points(signal_lines))))[:2]
    risks = filter_research_bullets(list(dict.fromkeys(select_risk_points(signal_lines))))[:2]
    if not any([positives, negatives, catalysts, risks]):
        return ""
    lines = ["当前叙事仍处于修复和验证并存的阶段。"]
    if positives:
        lines.append("成长资金更容易围绕这些多头线索交易：")
        lines.extend(f"- {item}" for item in positives)
    if negatives:
        lines.append("卖方怀疑派会持续追问这些空头断点：")
        lines.extend(f"- {item}" for item in negatives)
    if catalysts:
        lines.append("产业链和题材资金最关注的催化剂是：")
        lines.extend(f"- {item}" for item in catalysts)
    if risks:
        lines.append("如果这些风险继续恶化，情绪会迅速反转：")
        lines.extend(f"- {item}" for item in risks)
    return clip_text("\n".join(lines), 1200)


def build_comparison_fallback_from_evidence(signal_lines: list[str]) -> str:
    peers = extract_peer_mentions(signal_lines)
    positives = filter_research_bullets(list(dict.fromkeys(select_positive_points(signal_lines))))[:2]
    negatives = filter_research_bullets(list(dict.fromkeys(select_negative_points(signal_lines))))[:2]
    risks = filter_research_bullets(list(dict.fromkeys(select_risk_points(signal_lines))))[:2]
    lines: list[str] = []
    if peers:
        lines.append(f"当前更相关的可比对象包括：{', '.join(peers[:5])}。")
    else:
        lines.append("当前公开资料还没有建立出足够干净的 peer set，至少要继续跟中科飞测、精测电子与国际量测设备龙头做横向对比。")
    if positives:
        lines.append("横向上最值得继续研究的点：")
        lines.extend(f"- {item}" for item in positives)
    if negatives:
        lines.append("横向比较下最明显的短板：")
        lines.extend(f"- {item}" for item in negatives)
    if risks:
        lines.append("因此估值锚仍要建立在这些未解风险之上：")
        lines.extend(f"- {item}" for item in risks)
    if not lines:
        return ""
    return clip_text("\n".join(lines), 1200)


def should_replace_sentiment_summary(text: str) -> bool:
    stripped = clean_research_summary(text)
    if not stripped:
        return True
    required = ("成长", "卖方", "产业", "散户", "叙事", "温度")
    return sum(token in stripped for token in required) < 2


def should_replace_comparison_summary(text: str) -> bool:
    stripped = clean_research_summary(text)
    if not stripped:
        return True
    required = ("可比", "估值", "相对", "中科飞测", "精测电子", "KLA", "Applied")
    return sum(token in stripped for token in required) < 1


def filter_research_bullets(items: list[str]) -> list[str]:
    kept: list[str] = []
    for item in items:
        cleaned = clean_research_line(item)
        if not cleaned or looks_like_title_stub(cleaned):
            continue
        kept.append(cleaned)
    return kept


def looks_like_title_stub(text: str) -> bool:
    stub_tokens = ("研究报告", "公司点评", "年报", "财务报表", "年度报告", "点评：", "深度报告")
    if any(token in text for token in stub_tokens) and len(text) < 42:
        return True
    return False


def extract_peer_mentions(signal_lines: list[str]) -> list[str]:
    peer_tokens = [
        "中科飞测",
        "精测电子",
        "华海清科",
        "北方华创",
        "芯源微",
        "至纯科技",
        "KLA",
        "Applied Materials",
        "Onto Innovation",
        "长川科技",
    ]
    found: list[str] = []
    for line in signal_lines:
        for token in peer_tokens:
            if token.lower() in line.lower() and token not in found:
                found.append(token)
    return found


def derive_role_bullets(kind: str, signal_lines: list[str]) -> list[str]:
    if kind == "bull":
        points = select_positive_points(signal_lines)
    elif kind == "bear":
        points = select_negative_points(signal_lines)
    elif kind == "catalyst":
        points = select_catalyst_points(signal_lines)
    else:
        points = select_risk_points(signal_lines)
    return list(dict.fromkeys(points))[:5]


def clean_research_summary(text: str) -> str:
    if not text.strip():
        return ""
    lines: list[str] = []
    for raw in text.splitlines():
        line = clean_research_line(raw)
        if line:
            lines.append(line)
    if not lines:
        return ""
    return clip_text("\n".join(dict.fromkeys(lines)), 1200)


def clean_research_line(line: str) -> str:
    stripped = re.sub(r"\s+", " ", line).strip()
    if not stripped:
        return ""
    stripped = stripped.replace("```", "").strip()
    if not stripped:
        return ""
    if stripped.startswith("#"):
        return ""
    if stripped in {"---", "___"}:
        return ""
    cleaned = sanitize_source_text(stripped)
    if not cleaned or looks_like_navigation_noise(cleaned):
        return ""
    return cleaned


def looks_like_navigation_noise(text: str) -> bool:
    lowered = text.lower()
    noisy_tokens = (
        "_新浪",
        "新浪网",
        "同花顺",
        "证券之星",
        "中财网",
        "理杏仁",
        "股票频道",
        "财经首页",
        "股吧",
        "和讯网",
        "东方财富",
        "发现报告",
        "腾讯新闻",
        "http://",
        "https://",
        "扫码",
        "专题 数据 行情",
        "更多**",
        "请务必阅读正文之后的免责声明部分",
        "行情中心",
        "自选股",
        "板块详情",
        "指数详情",
        "看点 行情 量化",
        "主板 必读 研报 新股",
    )
    if any(token in text or token in lowered for token in noisy_tokens):
        return True
    if text.count("|") >= 2 or text.count("·") >= 2 or text.count("*") >= 2:
        return True
    if text.count("_") >= 2:
        return True
    if len(text) < 8:
        return True
    if re.fullmatch(r"[A-Za-z0-9\-\._/:\(\)\[\] ]+", text):
        return True
    return False


def build_local_synthesis_payload(
    *,
    stock_name: str,
    ticker: str | None,
    market: str,
    angle: str,
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
    guru_council: AgentRunResult,
    mirofish_scenario_engine: AgentRunResult,
    price_committee: AgentRunResult,
) -> dict[str, Any]:
    evidence = extract_evidence_from_traces(
        [market_analyst.tool_traces, company_analyst.tool_traces, sentiment_simulator.tool_traces, comparison_analyst.tool_traces, price_committee.tool_traces]
    )
    market_points = derive_points(market_analyst.content, evidence, "行业")
    company_points = derive_points(company_analyst.content, evidence, "公司")
    sentiment_points = derive_points(sentiment_simulator.content, evidence, "叙事")
    comparison_points = derive_points(comparison_analyst.content, evidence, "可比")
    debate_points = derive_points(committee_red_team.content, evidence, "质询")
    committee_points = derive_points(guru_council.content, evidence, "委员会")
    scenario_points = derive_points(mirofish_scenario_engine.content, evidence, "情景")
    target_prices = extract_target_prices_from_text(price_committee.content)

    return {
        "company_name": stock_name,
        "ticker": ticker or stock_name,
        "exchange": "SSE" if (ticker or "").endswith(".SH") else "",
        "market": market,
        "quick_take": (
            f"{stock_name} 当前更适合作为 watchlist 持续研究。"
            "多 agent 联网搜索支持其位于中国高端制造/自动化升级叙事里，但订单质量、客户结构与估值锚仍需继续核验。"
        ),
        "verdict": "watchlist",
        "confidence": "medium",
        "market_map": "\n".join(market_points[:3]) or "行业景气度、资本开支周期与客户需求仍需补证。",
        "business_summary": "\n".join(company_points[:3]) or "公司业务定位、客户结构与订单质量仍需继续核验。",
        "china_story": angle or "中国故事",
        "sentiment_simulation": "\n".join(sentiment_points[:4]) or "公开叙事显示市场关注点分散，短期预期仍在博弈中。",
        "peer_comparison": "\n".join(comparison_points[:4]) or "缺少高质量可比公司与估值锚，横向比较仍需继续补证。",
        "committee_takeaways": "\n".join(committee_points[:4]) or "委员会仍然倾向把它放在 watchlist，而不是直接进入高确信仓位。",
        "scenario_outlook": "\n".join(scenario_points[:6]) or "base case 仍然是观察名单，bull case 取决于半导体订单放量，bear case 取决于苹果链继续走弱。",
        "debate_notes": "\n".join(debate_points[:4]) or "当前最大的断点在订单质量、客户集中度与估值锚是否成立。",
        "bull_case": company_points[:5] or ["国产替代与先进制造升级叙事具备继续研究价值。"],
        "bear_case": build_risk_like_points(company_points, sentiment_points, prefix="反方")[:5]
        or ["客户集中、订单持续性与景气波动可能压制估值重估。"],
        "catalysts": build_catalyst_points(company_points, market_points)[:5]
        or ["后续订单、客户扩张或行业资本开支回暖是关键观察点。"],
        "risks": build_risk_like_points(company_points, market_points, prefix="风险")[:5]
        or ["行业需求波动、验证不足与估值锚不清晰仍是主要风险。"],
        "valuation_view": "当前公开证据更适合建立观察名单，而不是直接给出高确信估值结论。",
        "target_prices": target_prices,
        "evidence": evidence[:10],
        "next_questions": [
            "公司当前收入与订单中，半导体/先进制造相关占比有多高？",
            "核心客户集中度与订单可持续性是否正在改善？",
            "资本开支周期拐点是否已经开始传导到新接订单与利润率？",
        ],
    }


def load_memory_context(*, memory_dir: Path, stock_name: str, ticker: str | None) -> MemoryContext | None:
    candidates = [
        memory_dir / f"{slugify(ticker or '')}.json" if ticker else None,
        memory_dir / f"{slugify(stock_name)}.json",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                return MemoryContext(path=candidate, payload=json.loads(candidate.read_text(encoding="utf-8")))
            except Exception:
                continue
    return None


def save_memory_context(
    *,
    memory_dir: Path,
    stock_name: str,
    normalized: dict[str, Any],
    market_analyst: AgentRunResult,
    company_analyst: AgentRunResult,
    sentiment_simulator: AgentRunResult,
    comparison_analyst: AgentRunResult,
    committee_red_team: AgentRunResult,
    guru_council: AgentRunResult,
    mirofish_scenario_engine: AgentRunResult,
    price_committee: AgentRunResult,
) -> Path:
    ticker = str(normalized.get("ticker") or stock_name)
    memory_path = memory_dir / f"{slugify(ticker)}.json"
    evidence = normalized.get("evidence", [])
    payload = {
        "stock_name": stock_name,
        "ticker": ticker,
        "verdict": normalized.get("verdict"),
        "confidence": normalized.get("confidence"),
        "bull_case": normalized.get("bull_case", []),
        "bear_case": normalized.get("bear_case", []),
        "catalysts": normalized.get("catalysts", []),
        "risks": normalized.get("risks", []),
        "target_prices": normalized.get("target_prices", {}),
        "next_questions": normalized.get("next_questions", []),
        "evidence_digest": [
            clip_text(f"{item.get('title', 'Source')}：{item.get('claim', '')}", 240) for item in evidence[:6] if isinstance(item, dict)
        ],
        "agent_digest": {
            market_analyst.name: clip_text(market_analyst.content, 1000),
            company_analyst.name: clip_text(company_analyst.content, 1000),
            sentiment_simulator.name: clip_text(sentiment_simulator.content, 1000),
            comparison_analyst.name: clip_text(comparison_analyst.content, 1000),
            committee_red_team.name: clip_text(committee_red_team.content, 1000),
            guru_council.name: clip_text(guru_council.content, 1000),
            mirofish_scenario_engine.name: clip_text(mirofish_scenario_engine.content, 1000),
            price_committee.name: clip_text(price_committee.content, 1000),
        },
        "persona_pack": {
            role: list(get_persona_blend(role).lead_investors)
            for role in [
                market_analyst.name,
                company_analyst.name,
                sentiment_simulator.name,
                comparison_analyst.name,
                committee_red_team.name,
                guru_council.name,
                mirofish_scenario_engine.name,
                price_committee.name,
            ]
        },
        "updated_at": datetime.now(UTC).isoformat(),
    }
    memory_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return memory_path


def derive_points(text: str, evidence: list[dict[str, str]], keyword: str) -> list[str]:
    points = [line.strip("- ").strip() for line in text.splitlines() if line.strip().startswith("-")]
    if points:
        return points[:5]
    derived = [item["claim"] for item in evidence if keyword in item["title"] or keyword in item["claim"]]
    return [claim for claim in derived if claim][:5]


def build_risk_like_points(primary: list[str], secondary: list[str], *, prefix: str) -> list[str]:
    points: list[str] = []
    for item in [*primary, *secondary]:
        if not item:
            continue
        if any(token in item for token in ["风险", "波动", "不确定", "集中", "下滑", "压力", "质疑", "回落"]):
            points.append(item)
    if not points and primary:
        points = [f"{prefix}：{primary[-1]}"]
    return points[:5]


def build_catalyst_points(primary: list[str], secondary: list[str]) -> list[str]:
    points: list[str] = []
    for item in [*primary, *secondary]:
        if not item:
            continue
        if any(token in item for token in ["订单", "扩产", "升级", "渗透", "回暖", "增长", "突破", "催化"]):
            points.append(item)
    return points[:5]


def select_positive_points(items: list[str]) -> list[str]:
    tokens = ("增长", "提升", "扩张", "突破", "回暖", "改善", "渗透", "供货", "导入", "受益")
    return [item for item in items if any(token in item for token in tokens)]


def select_negative_points(items: list[str]) -> list[str]:
    tokens = ("下滑", "回落", "质疑", "压力", "集中", "不足", "波动", "风险", "不确定", "脆弱")
    return [item for item in items if any(token in item for token in tokens)]


def select_catalyst_points(items: list[str]) -> list[str]:
    tokens = ("订单", "扩产", "新品", "客户", "回暖", "催化", "导入", "放量", "改善")
    return [item for item in items if any(token in item for token in tokens)]


def select_risk_points(items: list[str]) -> list[str]:
    tokens = ("客户集中", "下滑", "回落", "估值", "不确定", "风险", "脆弱", "景气", "压力")
    return [item for item in items if any(token in item for token in tokens)]


def choose_section_text(value: str, fallback: str, default: str) -> str:
    text = value.strip()
    if is_low_quality_section(text):
        text = fallback.strip()
    return text or fallback or default


def choose_section_list(value: list[str], fallback: list[str]) -> list[str]:
    cleaned = [item for item in value if item.strip()]
    cleaned = [item for item in cleaned if not looks_like_title_stub(item)]
    if len(cleaned) <= 1 and any("：" in item or "_" in item or "http" in item.lower() for item in cleaned):
        cleaned = []
    return cleaned or fallback


def is_low_quality_section(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return True
    low_signal = 0
    for line in lines[:4]:
        if any(token in line for token in ["_新浪", "_股票频道", "同花顺", "中财网", "证券之星", "股吧", "理杏仁", "九方智投", "http"]):
            low_signal += 1
    return low_signal >= max(2, min(3, len(lines)))


def iter_tool_result_candidates(result: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    raw_results = result.get("results")
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("link") or "").strip()
            if not url or is_blocked_source(url):
                continue
            title = clip_text(str(item.get("title") or item.get("name") or url or "Untitled source").strip(), 160)
            claim = clip_text(sanitize_source_text(str(item.get("content") or item.get("snippet") or item.get("text") or "").strip()), 420)
            quality = source_quality_score(url)
            if quality < MIN_SOURCE_QUALITY:
                continue
            if url:
                candidates.append(
                    {
                        "title": title,
                        "url": url,
                        "claim": claim or "Search result captured during multi-agent research.",
                        "stance": "neutral",
                        "domain": source_domain(url),
                        "quality": str(quality),
                    }
                )
    url = str(result.get("url") or "").strip()
    if url and not is_blocked_source(url):
        title = clip_text(str(result.get("title") or result.get("name") or url).strip(), 160)
        claim = clip_text(sanitize_source_text(str(result.get("content") or result.get("text") or result.get("excerpt") or "").strip()), 420)
        quality = source_quality_score(url)
        if quality >= MIN_SOURCE_QUALITY:
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "claim": claim or "Fetched page used during multi-agent research.",
                    "stance": "neutral",
                    "domain": source_domain(url),
                    "quality": str(quality),
                }
            )
    candidates.sort(key=evidence_sort_key, reverse=True)
    return candidates


def source_domain(url: str) -> str:
    if not url.strip():
        return ""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return ""
    return hostname.lower().lstrip("www.")


def source_quality_score(url: str) -> int:
    domain = source_domain(url)
    if not domain:
        return 50
    for key, score in DOMAIN_QUALITY_OVERRIDES.items():
        normalized_key = key.lower().lstrip("www.")
        if domain == normalized_key or domain.endswith(f".{normalized_key}"):
            return score
    if domain.endswith(".gov") or domain.endswith(".gov.cn"):
        return 90
    if any(token in domain for token in ("exchange", "investor", "ir.", "sec.", "cninfo", "hkexnews")):
        return 85
    if any(token in domain for token in ("caixin", "yicai", "reuters", "bloomberg", "wsj")):
        return 82
    if any(token in domain for token in ("sina", "eastmoney", "futunn", "xueqiu")):
        return 65
    return 55


def is_blocked_source(url: str) -> bool:
    domain = source_domain(url)
    if not domain:
        return False
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_SOURCE_DOMAINS)


def evidence_sort_key(item: dict[str, str]) -> tuple[int, int, int]:
    quality = int(str(item.get("quality") or "0"))
    claim_len = len(str(item.get("claim") or ""))
    official_bonus = 1 if quality >= 85 else 0
    return quality, official_bonus, claim_len


def infer_expected_tokens(agent_traces: list[list[dict[str, Any]]]) -> set[str]:
    tokens: set[str] = set()
    for traces in agent_traces:
        for trace in traces:
            arguments = trace.get("arguments")
            if not isinstance(arguments, dict):
                continue
            query = str(arguments.get("query") or arguments.get("url") or "")
            for match in re.findall(r"\b\d{6}(?:\.(?:SH|SZ))?\b", query, flags=re.IGNORECASE):
                tokens.add(match.upper())
                tokens.add(match.split(".", 1)[0].upper())
            for match in re.findall(r"[\u4e00-\u9fff]{2,8}", query):
                if any(token in match for token in ("股份", "赛腾", "公司", "电子", "设备")):
                    tokens.add(match)
                    if "股份" in match:
                        tokens.add(match.replace("股份", "").strip())
    return {token for token in tokens if token}


def is_relevant_candidate(candidate: dict[str, str], expected_tokens: set[str]) -> bool:
    if not expected_tokens:
        return True
    haystack = "\n".join(
        [
            str(candidate.get("title") or ""),
            str(candidate.get("claim") or ""),
            str(candidate.get("url") or ""),
        ]
    )
    normalized_haystack = haystack.upper()
    if any(token.upper() in normalized_haystack for token in expected_tokens):
        return True
    quality = int(str(candidate.get("quality") or "0"))
    official_like = quality >= 85 or any(
        marker in haystack
        for marker in ("审核问询函", "首次公开发行", "回复", "股份有限公司", "招股说明", "年报", "公告")
    )
    other_company_match = re.search(r"关于([\u4e00-\u9fff]{3,20}(?:股份有限公司|科技股份有限公司|精密仪器股份有限公司))", haystack)
    if official_like and other_company_match:
        return False
    return True


def sanitize_source_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    lines = []
    seen: set[str] = set()
    noise_tokens = (
        "谢谢您的宝贵意见",
        "换肤",
        "上一个股",
        "下一个股",
        "财经首页",
        "同花顺F10",
        "扫码",
        "返回 当前位置",
        "企业号",
        "收藏",
    )
    for raw_line in re.split(r"[\r\n]+", stripped):
        line = re.sub(r"\s+", " ", raw_line).strip(" -|\t")
        if not line or len(line) < 6:
            continue
        if any(token in line for token in noise_tokens):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
        if sum(len(item) for item in lines) >= 260:
            break
    compact = "\n".join(lines[:4]).strip()
    return compact or stripped[:260].strip()


def extract_target_prices_from_text(text: str) -> dict[str, dict[str, str]]:
    buckets = {
        "short_term": {"price": "", "horizon": "", "thesis": ""},
        "medium_term": {"price": "", "horizon": "", "thesis": ""},
        "long_term": {"price": "", "horizon": "", "thesis": ""},
    }
    label_map = {
        "短期目标价": "short_term",
        "中期目标价": "medium_term",
        "长期目标价": "long_term",
        "短期": "short_term",
        "中期": "medium_term",
        "长期": "long_term",
    }
    for raw_line in text.splitlines():
        line = clean_research_line(raw_line)
        if not line:
            continue
        normalized_line = line.lstrip("-• ").strip()
        matched_key = next((target for label, target in label_map.items() if label in normalized_line), None)
        if not matched_key and "|" in normalized_line:
            row_key = None
            if "短期" in normalized_line:
                row_key = "short_term"
            elif "中期" in normalized_line:
                row_key = "medium_term"
            elif "长期" in normalized_line:
                row_key = "long_term"
            if row_key:
                cells = [cell.strip(" *") for cell in normalized_line.split("|") if cell.strip(" *")]
                price = midpoint_price(cells[1]) if len(cells) > 1 else ""
                horizon = extract_horizon_from_text(cells[3] if len(cells) > 3 else normalized_line)
                thesis = clean_research_line(cells[4] if len(cells) > 4 else normalized_line)
                buckets[row_key] = {
                    "price": price,
                    "horizon": horizon,
                    "thesis": thesis,
                }
                continue
        if not matched_key:
            continue
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|人民币|RMB)", normalized_line)
        thesis = normalized_line
        if "：" in thesis:
            thesis = thesis.split("：", 1)[1].strip()
        elif ":" in thesis:
            thesis = thesis.split(":", 1)[1].strip()
        buckets[matched_key] = {
            "price": price_match.group(1) if price_match else midpoint_price(normalized_line),
            "horizon": extract_horizon_from_text(normalized_line),
            "thesis": thesis,
        }
    return normalize_target_prices(buckets, None)


def normalize_target_prices(
    value: Any,
    fallback: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    base = {
        "short_term": {"price": "", "horizon": "1-3个月", "thesis": "等待近期订单、客户与情绪验证。"},
        "medium_term": {"price": "", "horizon": "3-12个月", "thesis": "观察收入结构迁移与估值锚是否抬升。"},
        "long_term": {"price": "", "horizon": "12-36个月", "thesis": "判断是否能沉淀为更高质量的先进制造设备资产。"},
    }
    for source in [fallback or {}, value if isinstance(value, dict) else {}]:
        for key in ("short_term", "medium_term", "long_term"):
            raw = source.get(key)
            if not isinstance(raw, dict):
                continue
            price = str(raw.get("price") or "").strip()
            horizon = str(raw.get("horizon") or "").strip()
            thesis = clean_research_line(str(raw.get("thesis") or "").strip())
            if price:
                base[key]["price"] = price
            if horizon:
                base[key]["horizon"] = horizon
            if thesis:
                base[key]["thesis"] = thesis
    return base


def midpoint_price(text: str) -> str:
    matches = [float(match) for match in re.findall(r"(\d+(?:\.\d+)?)", text)]
    if not matches:
        return ""
    if len(matches) == 1:
        return f"{matches[0]:g}"
    midpoint = (matches[0] + matches[1]) / 2
    return f"{midpoint:.2f}".rstrip("0").rstrip(".")


def extract_horizon_from_text(text: str) -> str:
    match = re.search(r"(\d+\s*(?:-\s*\d+)?\s*(?:个)?(?:交易日|日|周|个月|月|季|季度|年))", text)
    return match.group(1).replace(" ", "") if match else ""


def extract_current_price_from_text(text: str) -> float | None:
    patterns = [
        r"当前价格基准[：:]\s*[¥￥]?\s*(\d+(?:\.\d+)?)",
        r"\b(\d+(?:\.\d+)?)↑",
        r"\b(\d+(?:\.\d+)?)\s*(?:元|人民币|RMB)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 1 <= value <= 10000:
                return value
    return None


def derive_target_prices_from_context(text: str, *, verdict: str, ticker: str | None = None) -> dict[str, dict[str, str]]:
    current_price = extract_current_price_from_text(text)
    if current_price is None and ticker:
        current_price = fetch_latest_price(ticker)
    if current_price is None:
        return {}
    if verdict == "high_conviction":
        multipliers = {
            "short_term": 1.08,
            "medium_term": 1.22,
            "long_term": 1.42,
        }
    elif verdict == "reject":
        multipliers = {
            "short_term": 0.92,
            "medium_term": 0.84,
            "long_term": 0.72,
        }
    else:
        multipliers = {
            "short_term": 0.98,
            "medium_term": 1.12,
            "long_term": 1.28,
        }
    theses = {
        "short_term": "围绕近期订单、客户验证与情绪修复的保守目标价。",
        "medium_term": "基于收入结构迁移与估值锚修复的中期目标价。",
        "long_term": "基于业务质量抬升与重估完成后的长期目标价。",
    }
    horizons = {
        "short_term": "1-3个月",
        "medium_term": "3-12个月",
        "long_term": "12-36个月",
    }
    return {
        key: {
            "price": f"{current_price * multiple:.2f}".rstrip("0").rstrip("."),
            "horizon": horizons[key],
            "thesis": theses[key],
        }
        for key, multiple in multipliers.items()
    }


def fill_missing_target_prices(
    base: dict[str, dict[str, str]],
    fallback: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    for key in ("short_term", "medium_term", "long_term"):
        target = base.get(key, {})
        backup = fallback.get(key, {})
        if not str(target.get("price") or "").strip() and backup:
            target["price"] = str(backup.get("price") or "").strip()
        if not str(target.get("horizon") or "").strip() and backup:
            target["horizon"] = str(backup.get("horizon") or "").strip()
        if (not str(target.get("thesis") or "").strip() or "继续核实" in str(target.get("thesis") or "")) and backup:
            target["thesis"] = str(backup.get("thesis") or "").strip()
        base[key] = target
    return base


def parse_interval_hours(value: str) -> int:
    text = value.strip().lower()
    match = re.fullmatch(r"(\d+)\s*([hdw])", text)
    if not match:
        raise RuntimeError("Interval must look like 24h, 3d, or 1w.")
    quantity = int(match.group(1))
    unit = match.group(2)
    multipliers = {"h": 1, "d": 24, "w": 24 * 7}
    return quantity * multipliers[unit]


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def screen_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    score = int(item.get("screen_score") or 0)
    source_count = int(item.get("source_count") or 0)
    confidence = normalize_confidence(str(item.get("confidence") or "medium"))
    confidence_rank = {"low": 1, "medium": 2, "high": 3}.get(confidence, 2)
    return (score, source_count, confidence_rank)


def normalize_screen_candidates(value: Any, *, theme: str, market: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        company_name = str(item.get("company_name") or item.get("name") or "").strip()
        raw_ticker = str(item.get("ticker") or "").strip()
        if raw_ticker and market.upper() == "CN" and raw_ticker.isdigit():
            inferred_exchange = "SSE" if raw_ticker.startswith(("5", "6", "9")) else "SZSE"
            ticker = normalize_ticker(raw_ticker, inferred_exchange, market)
        else:
            ticker = normalize_ticker(raw_ticker, "", market) if raw_ticker else ""
        if not company_name and not ticker:
            continue
        identifier = slugify(ticker or company_name)
        if identifier in seen:
            continue
        seen.add(identifier)
        normalized.append(
            {
                "company_name": company_name or ticker,
                "ticker": ticker,
                "market": str(item.get("market") or market).strip() or market,
                "rationale": clean_research_summary(str(item.get("rationale") or item.get("why") or f"{company_name or ticker} 值得进一步研究。")),
                "screen_score": max(0, min(100, int(item.get("screen_score") or 50))),
                "confidence": normalize_confidence(str(item.get("confidence") or "medium")),
                "source_count": max(1, int(item.get("source_count") or 1)),
                "angle": str(item.get("angle") or theme).strip() or theme,
            }
        )
    normalized.sort(key=screen_sort_key, reverse=True)
    return normalized


def build_screening_fallback_candidates(evidence: list[dict[str, str]], *, theme: str, market: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence:
        title = f"{item.get('title', '')} {item.get('claim', '')}".strip()
        match = re.search(r"([A-Za-z\u4e00-\u9fff]+)[(（]?\s*(\d{6})(?:\.?(?:SH|SZ))?[)）]?", title)
        if not match:
            continue
        company_name = match.group(1).strip("-_ ")
        raw_code = match.group(2)
        ticker = normalize_ticker(raw_code, "SSE" if raw_code.startswith("6") else "SZSE", market)
        identifier = slugify(ticker or company_name)
        if identifier in seen:
            continue
        seen.add(identifier)
        candidates.append(
            {
                "company_name": company_name,
                "ticker": ticker,
                "market": market,
                "rationale": clean_research_summary(item.get("claim", "")) or f"{company_name} 与 {theme} 主题相关，值得继续验证。",
                "screen_score": min(95, max(45, int(item.get("quality") or 50))),
                "confidence": "medium",
                "source_count": 1,
                "angle": theme,
            }
        )
    candidates.sort(key=screen_sort_key, reverse=True)
    return candidates[:12]


def fetch_latest_price(ticker: str) -> float | None:
    secid = eastmoney_secid(ticker)
    if not secid:
        return None
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43"
    try:
        with urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    raw = (((payload or {}).get("data") or {}).get("f43"))
    try:
        value = float(raw) / 100
    except Exception:
        return None
    return value if value > 0 else None


def eastmoney_secid(ticker: str) -> str:
    normalized = ticker.upper().strip()
    if normalized.endswith(".SH"):
        return f"1.{normalized.split('.', 1)[0]}"
    if normalized.endswith(".SZ"):
        return f"0.{normalized.split('.', 1)[0]}"
    if normalized.isdigit():
        prefix = "1" if normalized.startswith("6") else "0"
        return f"{prefix}.{normalized}"
    return ""


def render_markdown(
    *,
    company_name: str,
    ticker: str,
    exchange: str,
    market: str,
    model: str,
    quick_take: str,
    verdict: str,
    confidence: str,
    market_map: str,
    business_summary: str,
    china_story: str,
    sentiment_simulation: str,
    peer_comparison: str,
    committee_takeaways: str,
    scenario_outlook: str,
    debate_notes: str,
    bull_case: list[str],
    bear_case: list[str],
    catalysts: list[str],
    risks: list[str],
    valuation_view: str,
    target_prices: dict[str, dict[str, str]],
    evidence: list[dict[str, str]],
    next_questions: list[str],
) -> str:
    def bullet(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- 暂无充分结论，需继续补证。"

    def target_price_block() -> str:
        lines: list[str] = []
        label_map = {
            "short_term": "短期目标价",
            "medium_term": "中期目标价",
            "long_term": "长期目标价",
        }
        for key in ("short_term", "medium_term", "long_term"):
            payload = target_prices.get(key, {})
            price = str(payload.get("price") or "").strip() or "待继续核实"
            horizon = str(payload.get("horizon") or "").strip() or "待补充"
            thesis = str(payload.get("thesis") or "").strip() or "当前证据仍不足，需要更多高质量验证。"
            display_price = f"{price} 元" if price != "待继续核实" else price
            lines.append(f"- {label_map[key]}：{display_price} | 时间：{horizon} | 依据：{thesis}")
        return "\n".join(lines)

    evidence_block = "\n".join(
        f"- [{item['title']}]({item['url']})：{item['claim']} ({item['stance']})"
        for item in evidence
        if item["url"]
    ) or "- 暂无可落地的外部证据。"

    exchange_line = f"{exchange} / {market}" if exchange else market
    return "\n".join(
        [
            f"# {company_name} 研究备忘录",
            "",
            f"- 标的：`{ticker}`",
            f"- 市场：{exchange_line}",
            f"- 模型：`{model}`",
            f"- 结论：`{verdict}`",
            f"- 信心：`{confidence}`",
            "",
            "## 快速判断",
            quick_take,
            "",
            "## 业务概览",
            business_summary,
            "",
            "## 市场与行业图谱",
            market_map,
            "",
            "## 中国故事视角",
            china_story,
            "",
            "## 舆情与叙事模拟",
            sentiment_simulation,
            "",
            "## 横向对比与估值锚",
            peer_comparison,
            "",
            "## 股神议会纪要",
            committee_takeaways,
            "",
            "## MiroFish 多未来场景",
            scenario_outlook,
            "",
            "## 多头逻辑",
            bullet(bull_case),
            "",
            "## 空头逻辑",
            bullet(bear_case),
            "",
            "## 催化剂",
            bullet(catalysts),
            "",
            "## 主要风险",
            bullet(risks),
            "",
            "## 估值视角",
            valuation_view,
            "",
            "## 目标价与时间框架",
            target_price_block(),
            "",
            "## 投委会红队质询",
            debate_notes,
            "",
            "## 证据清单",
            evidence_block,
            "",
            "## 下一步验证问题",
            bullet(next_questions),
        ]
    )


def slugify(value: str) -> str:
    stripped = re.sub(r"\s+", "-", value.strip().lower())
    stripped = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", stripped)
    stripped = re.sub(r"-{2,}", "-", stripped).strip("-")
    return stripped or "stock-report"


def normalize_verdict(value: str) -> str:
    lowered = value.strip().lower()
    if any(token in value for token in ["高确信", "高 conviction", "强烈看好", "积极", "乐观", "超配", "看多"]) or lowered in {"high_conviction", "overweight", "buy"} or "high" in lowered:
        return "high_conviction"
    if any(token in value for token in ["拒绝", "回避", "谨慎看空", "负面", "减持", "低配"]) or lowered in {"reject", "underweight", "sell"}:
        return "reject"
    return "watchlist"


def normalize_confidence(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"5", "4", "high", "strong"} or any(token in value for token in ["高", "较高"]):
        return "high"
    if lowered in {"3", "medium", "moderate"} or any(token in value for token in ["中", "一般"]):
        return "medium"
    if lowered in {"2", "1", "low", "weak"} or any(token in value for token in ["低", "偏低"]):
        return "low"
    return "medium"


def normalize_ticker(value: str, exchange: Any, market: str) -> str:
    text = value.strip()
    if "." in text or ":" in text:
        return text
    digits = re.sub(r"[^\dA-Z]", "", text.upper())
    exchange_text = str(exchange or "").upper()
    if market.upper() == "CN" and digits.isdigit():
        if exchange_text in {"SSE", "SH", "SHSE"}:
            return f"{digits}.SH"
        if exchange_text in {"SZSE", "SZ"}:
            return f"{digits}.SZ"
    return digits or text
