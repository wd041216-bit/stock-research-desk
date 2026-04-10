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

from .documents import (
    build_english_report_fallback,
    build_english_screening_fallback,
    build_screening_doc_payload,
    contains_cjk,
    write_bilingual_report_docx,
    write_bilingual_screening_docx,
    write_bilingual_watchlist_digest_docx,
    write_report_docx,
    write_screening_docx,
    write_watchlist_digest_docx,
)
from .persona_pack import get_persona_blend, render_persona_instruction
from .runtime import parse_structured_response


DEFAULT_HOST = "https://ollama.com"
DEFAULT_MODEL = "kimi-k2.5:cloud"
CROSS_VALIDATED_SEARCH_ROOT = Path(__file__).resolve().parents[3] / "tmp" / "cross-validated-search"
REPO_ROOT = Path(__file__).resolve().parents[2]

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
US_LISTING_HINTS = {"US", "USA", "NASDAQ", "NYSE", "AMEX", "OTC", "OTCQX", "OTCQB"}
COMPANY_ACTION_VERBS = (
    "Announces",
    "Reports",
    "Builds",
    "Secures",
    "Drives",
    "Reaffirms",
    "Demonstrates",
    "Accepted",
    "Achieves",
    "Highlights",
    "Reinforces",
    "Launches",
    "Receives",
    "Provides",
    "Completes",
    "Advances",
)
TITLE_NOISE_PHRASES = (
    "Stock Price Today",
    "Stock Price",
    "Share Price",
    "Shares Outstanding",
    "Investor Relations",
    "Press Release",
    "Q1 2025",
    "Q2 2025",
    "Q3 2025",
    "Q4 2025",
)

SECTOR_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "match_tokens": ("脑机接口", "bci", "brain-computer", "brain computer"),
        "sector": "brain-computer interface",
        "keywords": (
            "brain-computer interface",
            "BCI",
            "neurotechnology",
            "neurostimulation",
            "implantable neurotech",
            "EEG headset",
            "closed-loop neuromodulation",
        ),
        "query_axes": (
            "listed brain-computer interface companies",
            "public neurotechnology companies with BCI exposure",
            "NASDAQ or OTC brain-computer interface stocks",
            "neurostimulation and brain-computer interface adjacent public names",
            "FDA clearance, commercial traction, and reimbursement milestones",
        ),
        "anchors": (
            {"company_name": "NeuroPace", "ticker": "NPCE", "market": "US"},
            {"company_name": "NeuroOne Medical Technologies", "ticker": "NMTC", "market": "US"},
            {"company_name": "Nexalin Technology", "ticker": "NXL", "market": "US"},
            {"company_name": "ONWARD Medical", "ticker": "ONWRY", "market": "US"},
            {"company_name": "Wearable Devices", "ticker": "WLDS", "market": "US"},
        ),
        "non_public_reference_names": ("Neuralink", "Synchron", "Blackrock Neurotech", "Paradromics"),
        "focus_questions": (
            "which names are truly public and tradable in the target market",
            "which names have real BCI or neuromodulation product exposure instead of vague concept adjacency",
            "which names have credible FDA, reimbursement, or commercialization milestones",
            "which names are only storytelling vehicles without real revenue traction",
        ),
    },
    {
        "match_tokens": ("人形机器人", "humanoid", "robotics", "机器人"),
        "sector": "humanoid robotics",
        "keywords": (
            "humanoid robotics",
            "embodied AI",
            "servo actuator",
            "robot joint reducer",
            "machine vision robotics",
            "industrial robotics",
        ),
        "query_axes": (
            "public humanoid robotics companies",
            "listed robot component suppliers with humanoid exposure",
            "actuator reducer servo and machine vision companies for humanoid robotics",
            "robotics commercialization backlog customer pipeline public companies",
            "which names are pure-play humanoid vs broad automation proxies",
        ),
        "anchors": (),
        "non_public_reference_names": ("Figure AI", "Agility Robotics", "1X", "Apptronik"),
        "focus_questions": (
            "which names are real public investable proxies or pure-play humanoid deployment names",
            "which names are only broad automation stories without humanoid relevance",
            "which companies have customer pilots backlog or production milestones",
        ),
    },
    {
        "match_tokens": ("核电", "nuclear", "smr", "small modular reactor"),
        "sector": "nuclear and SMR",
        "keywords": (
            "nuclear power",
            "SMR",
            "small modular reactor",
            "uranium fuel cycle",
            "nuclear services",
            "reactor component supplier",
        ),
        "query_axes": (
            "public SMR companies and nuclear suppliers",
            "listed uranium and fuel cycle equities",
            "nuclear service and reactor component public companies",
            "licensing milestones and deployment backlog for SMR companies",
            "which names are genuine nuclear exposure vs narrative passengers",
        ),
        "anchors": (),
        "non_public_reference_names": ("X-energy", "TerraPower"),
        "focus_questions": (
            "which listed names have actual licensing, fuel, service, or reactor economics",
            "which names rely mostly on policy narrative without near-term cash flow support",
        ),
    },
)


@dataclass(slots=True)
class WorkspacePaths:
    workspace_dir: Path
    reports_dir: Path
    memory_dir: Path
    screens_dir: Path
    digests_dir: Path
    artifacts_dir: Path
    watchlist_path: Path
    email_state_path: Path
    single_document_delivery: bool


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
    artifacts_dir: Path
    watchlist_path: Path
    single_document_delivery: bool


@dataclass(slots=True)
class AgentRunResult:
    name: str
    content: str
    tool_traces: list[dict[str, Any]]


@dataclass(slots=True)
class MemoryContext:
    path: Path | None
    payload: dict[str, Any]


def load_local_env_file(path: Path | None = None) -> None:
    env_path = path or (REPO_ROOT / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = os.path.expanduser(value)


def main(argv: list[str] | None = None) -> None:
    load_local_env_file()
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
        description="Run a multi-agent stock research workflow on Ollama Cloud and save local Chinese and English report documents."
    )
    parser.add_argument("identifier", help="Ticker or company name, for example: 603283.SH or 赛腾股份")
    parser.add_argument("market_positional", nargs="?", help="Optional market shorthand, for example: CN or US")
    parser.add_argument("--ticker", help="Optional ticker or exchange symbol hint. If omitted, ticker-like identifiers are used directly.")
    parser.add_argument("--market", default="", help="Market hint. Defaults to the positional market or CN.")
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
        request = resolve_research_request(
            identifier=args.identifier,
            ticker=args.ticker,
            market=args.market,
            market_positional=getattr(args, "market_positional", None),
        )
        config = load_config(
            model=args.model,
            think=args.think,
            max_results=args.max_results,
            max_fetches=args.max_fetches,
            timeout_seconds=args.timeout_seconds,
            output_dir=args.output_dir,
        )
        artifact = run_stock_research(
            stock_name=request["stock_name"],
            ticker=request["ticker"],
            market=request["market"],
            angle=args.angle,
            config=config,
            verbose=True,
        )
        if artifact["zh_docx_path"] == artifact["en_docx_path"]:
            print(f"Saved report document to: {artifact['primary_document_path']}")
        else:
            print(f"Saved Chinese report to: {artifact['zh_docx_path']}")
            print(f"Saved English report to: {artifact['en_docx_path']}")
        print(f"Saved internal machine payload to: {artifact['json_path']}")
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
        if artifact["zh_docx_path"] == artifact["en_docx_path"]:
            print(f"Saved screening document to: {artifact['primary_document_path']}")
        else:
            print(f"Saved Chinese screening brief to: {artifact['zh_docx_path']}")
            print(f"Saved English screening brief to: {artifact['en_docx_path']}")
        print(f"Saved internal screening payload to: {artifact['json_path']}")
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
                print(f"- {item['identifier']}: {item['primary_document_path']}")
            if result.get("digest_path") and result.get("zh_digest_path") == result.get("en_digest_path"):
                print(f"Saved watchlist digest to: {result['digest_path']}")
            else:
                if result.get("zh_digest_path"):
                    print(f"Saved Chinese watchlist digest to: {result['zh_digest_path']}")
                if result.get("en_digest_path"):
                    print(f"Saved English watchlist digest to: {result['en_digest_path']}")
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


def _is_within_workspace(path: Path, workspace_dir: Path) -> bool:
    try:
        path.resolve().relative_to(workspace_dir.resolve())
        return True
    except ValueError:
        return False


def resolve_workspace_paths(output_dir: str) -> WorkspacePaths:
    workspace_dir = default_workspace_home()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_dir).expanduser()
    reports_dir = output_path.resolve() if output_path.is_absolute() else (workspace_dir / output_path).resolve()
    memory_dir = (workspace_dir / "memory_palace").resolve()
    screens_dir = (workspace_dir / "screenings").resolve()
    digests_dir = (workspace_dir / "digests").resolve()
    artifacts_dir = (workspace_dir / ".internal").resolve()
    watchlist_path = (workspace_dir / "watchlist.json").resolve()
    email_state_path = (workspace_dir / "email_state.json").resolve()
    single_document_delivery = _is_within_workspace(reports_dir, workspace_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)
    screens_dir.mkdir(parents=True, exist_ok=True)
    digests_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "screenings").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "digests").mkdir(parents=True, exist_ok=True)
    return WorkspacePaths(
        workspace_dir=workspace_dir,
        reports_dir=reports_dir,
        memory_dir=memory_dir,
        screens_dir=screens_dir,
        digests_dir=digests_dir,
        artifacts_dir=artifacts_dir,
        watchlist_path=watchlist_path,
        email_state_path=email_state_path,
        single_document_delivery=single_document_delivery,
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
        artifacts_dir=paths.artifacts_dir,
        watchlist_path=paths.watchlist_path,
        single_document_delivery=paths.single_document_delivery,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
        timeout_seconds=config.timeout_seconds,
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
    document_paths = build_report_document_paths(
        reports_dir=config.reports_dir,
        timestamp=timestamp,
        slug=slug,
        single_document=config.single_document_delivery,
    )
    json_path = build_machine_artifact_path(
        artifacts_dir=config.artifacts_dir,
        category="reports",
        filename=f"{timestamp}-{slug}.json",
    )
    zh_payload = {**normalized, "model": config.model}
    en_payload = translate_structured_payload(
        client,
        model=config.model,
        think=config.think,
        timeout_seconds=config.timeout_seconds,
        payload=zh_payload,
        task_label="single-name stock research memo",
        fallback_payload=build_english_report_fallback(zh_payload),
    )
    if config.single_document_delivery:
        write_bilingual_report_docx(document_paths["primary"], zh_payload=zh_payload, en_payload=en_payload)
    else:
        write_report_docx(document_paths["zh"], payload=zh_payload, language="zh")
        write_report_docx(document_paths["en"], payload=en_payload, language="en")
    json_path.write_text(
        json.dumps(
            {
                **normalized,
                "document_paths": {
                    "primary": str(document_paths["primary"]),
                    "zh": str(document_paths["zh"]),
                    "en": str(document_paths["en"]),
                },
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
        "zh_docx_path": str(document_paths["zh"]),
        "en_docx_path": str(document_paths["en"]),
        "primary_document_path": str(document_paths["primary"]),
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
        timeout_seconds=config.timeout_seconds,
        theme=theme,
        desired_count=desired_count,
        market=market,
        seed_tickers=seed_tickers,
        max_results=config.max_results,
        max_fetches=config.max_fetches,
        verbose=verbose,
    )
    scout_evidence_candidates = build_screening_fallback_candidates(
        extract_evidence_from_traces([scout.get("tool_traces", [])]),
        theme=theme,
        market=market,
    )
    initial_candidates = normalize_screen_candidates(
        (scout.get("payload") or {}).get("candidates"),
        theme=theme,
        market=market,
    )
    initial_candidates = combine_candidate_lists(initial_candidates, scout_evidence_candidates, theme=theme, market=market)
    densified_payload: dict[str, Any] | None = None
    if len(initial_candidates) < max(3, desired_count * 2):
        if verbose:
            print(f"[screen] densifying candidate discovery from {len(initial_candidates)} names")
        densified_payload = run_screening_scout_densification(
            client=client,
            model=config.model,
            think=config.think,
            timeout_seconds=config.timeout_seconds,
            theme=theme,
            desired_count=desired_count,
            market=market,
            seed_tickers=seed_tickers,
            max_results=max(config.max_results + 2, 7),
            max_fetches=max(config.max_fetches + 3, 10),
            existing_candidates=initial_candidates,
            verbose=verbose,
        )
        densified_evidence_candidates = build_screening_fallback_candidates(
            extract_evidence_from_traces([densified_payload.get("tool_traces", [])]),
            theme=theme,
            market=market,
        )
        initial_candidates = combine_candidate_lists(
            initial_candidates,
            normalize_screen_candidates((densified_payload.get("payload") or {}).get("candidates"), theme=theme, market=market),
            densified_evidence_candidates,
            theme=theme,
            market=market,
        )
    initial_candidates = merge_seed_candidates(
        candidates=initial_candidates,
        seeds=build_seed_candidates(seed_tickers=seed_tickers, theme=theme, market=market),
    )
    if not initial_candidates:
        initial_candidates = scout_evidence_candidates
        initial_candidates = merge_seed_candidates(
            candidates=initial_candidates,
            seeds=build_seed_candidates(seed_tickers=seed_tickers, theme=theme, market=market),
        )
    if verbose:
        print(f"[screen] normalized candidates={len(initial_candidates)}")
    stage_one_count = min(max(desired_count * 4, desired_count + 4), len(initial_candidates))
    stage_one_seed = initial_candidates[:stage_one_count]
    if verbose:
        print(f"[screen] entering stage one diligence with {len(stage_one_seed)} candidates")
    stage_one: list[dict[str, Any]] = []
    for index, candidate in enumerate(stage_one_seed, start=1):
        if verbose:
            print(f"[screen] diligence {index}/{len(stage_one_seed)}: {candidate['company_name']} {candidate.get('ticker', '')}".strip())
        stage_one.append(
            run_screening_diligence(
                client=client,
                model=config.model,
                think=config.think,
                timeout_seconds=config.timeout_seconds,
                theme=theme,
                market=market,
                candidate=candidate,
                max_results=max(config.max_results + 2, 6),
                max_fetches=max(config.max_fetches + 3, 8),
                verbose=verbose,
            )
        )

    shortlist = run_second_screen_committee(
        client=client,
        model=config.model,
        think=config.think,
        timeout_seconds=config.timeout_seconds,
        theme=theme,
        market=market,
        desired_count=desired_count,
        candidates=stage_one,
        verbose=verbose,
    )
    if verbose:
        print(f"[screen] second screen returned {len(shortlist.get('recommended') or [])} recommendations")
    finalists = merge_screen_candidates(
        normalize_screen_candidates(shortlist.get("recommended"), theme=theme, market=market),
        references=stage_one,
    )[:desired_count]
    if not finalists:
        finalists = stage_one[:desired_count]
    if verbose:
        print(f"[screen] finalists={len(finalists)}")

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
                "zh_docx_path": artifact["zh_docx_path"],
                "en_docx_path": artifact["en_docx_path"],
                "primary_document_path": artifact["primary_document_path"],
                "json_path": artifact["json_path"],
                "payload": artifact.get("payload", {}),
            }
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = slugify(theme)
    document_paths = build_screening_document_paths(
        screens_dir=config.screens_dir,
        timestamp=timestamp,
        slug=f"{slug}-screening",
        single_document=config.single_document_delivery,
    )
    json_path = build_machine_artifact_path(
        artifacts_dir=config.artifacts_dir,
        category="screenings",
        filename=f"{timestamp}-{slug}-screening.json",
    )
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
    screening_doc_payload = build_screening_doc_payload(
        theme=theme,
        market=market,
        stage_one_candidates=stage_one,
        finalists=finalist_artifacts,
    )
    screening_doc_payload["generated_at"] = summary_payload["generated_at"]
    en_screening_payload = translate_structured_payload(
        client,
        model=config.model,
        think=config.think,
        timeout_seconds=config.timeout_seconds,
        payload=screening_doc_payload,
        task_label="theme screening summary",
        fallback_payload=build_english_screening_fallback(screening_doc_payload),
    )
    if config.single_document_delivery:
        write_bilingual_screening_docx(document_paths["primary"], zh_payload=screening_doc_payload, en_payload=en_screening_payload)
    else:
        write_screening_docx(document_paths["zh"], payload=screening_doc_payload, language="zh")
        write_screening_docx(document_paths["en"], payload=en_screening_payload, language="en")
    json_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "zh_docx_path": str(document_paths["zh"]),
        "en_docx_path": str(document_paths["en"]),
        "primary_document_path": str(document_paths["primary"]),
        "json_path": str(json_path),
        "report_paths": [item["primary_document_path"] for item in finalist_artifacts],
        "payload": summary_payload,
    }


def run_screening_scout(
    *,
    client: Client,
    model: str,
    think: str,
    timeout_seconds: float,
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
    planning_response = chat_with_guard(
        client,
        timeout_seconds=timeout_seconds,
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
            result = perform_search_with_fallback(client=client, market=market, **arguments)
        elif tool_name == "web_fetch":
            if fetch_count >= max_fetches:
                result = {"error": "fetch budget exhausted"}
            else:
                result = perform_fetch_with_fallback(client=client, **arguments)
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
        response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
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


def run_screening_scout_densification(
    *,
    client: Client,
    model: str,
    think: str,
    timeout_seconds: float,
    theme: str,
    desired_count: int,
    market: str,
    seed_tickers: list[str],
    max_results: int,
    max_fetches: int,
    existing_candidates: list[dict[str, Any]],
    verbose: bool = False,
) -> dict[str, Any]:
    system_prompt = build_screening_scout_prompt(max_results=max_results, max_fetches=max_fetches)
    user_prompt = build_screening_densification_user_prompt(
        theme=theme,
        desired_count=desired_count,
        market=market,
        seed_tickers=seed_tickers,
        existing_candidates=existing_candidates,
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_traces: list[dict[str, Any]] = []
    fetch_count = 0
    if verbose:
        print("[screen] scout densification")
    planning_response = chat_with_guard(
        client,
        timeout_seconds=timeout_seconds,
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
            result = perform_search_with_fallback(client=client, market=market, **arguments)
        elif tool_name == "web_fetch":
            if fetch_count >= max_fetches:
                result = {"error": "fetch budget exhausted"}
            else:
                result = perform_fetch_with_fallback(client=client, **arguments)
                fetch_count += 1
        else:
            result = {"error": f"unsupported tool: {tool_name}"}
        tool_traces.append({"tool_name": tool_name, "arguments": arguments, "result": result})

    synthesis_prompt = build_screening_densification_synthesis_prompt(
        theme=theme,
        desired_count=desired_count,
        market=market,
        evidence=extract_evidence_from_traces([tool_traces])[:16],
        seed_tickers=seed_tickers,
        existing_candidates=existing_candidates,
    )
    try:
        response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
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
    return {
        "payload": {
            "candidates": build_screening_fallback_candidates(
                extract_evidence_from_traces([tool_traces]),
                theme=theme,
                market=market,
            )
        },
        "tool_traces": tool_traces,
    }


def run_second_screen_committee(
    *,
    client: Client,
    model: str,
    think: str,
    timeout_seconds: float,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
    verbose: bool = False,
) -> dict[str, Any]:
    if verbose:
        print("[screen] council round 1: bull case")
    bull_round = safe_run_agent_with_tools(
        client=client,
        name="screening_council_bull",
        model=model,
        think=think,
        timeout_seconds=timeout_seconds,
        system_prompt=build_screening_council_bull_prompt(),
        user_prompt=build_screening_council_user_prompt(theme=theme, market=market, desired_count=desired_count, candidates=candidates),
        max_results=7,
        max_fetches=10,
        verbose=verbose,
    )
    if verbose:
        print("[screen] council round 2: red team")
    red_round = safe_run_agent_with_tools(
        client=client,
        name="screening_council_red_team",
        model=model,
        think=think,
        timeout_seconds=timeout_seconds,
        system_prompt=build_screening_council_red_prompt(),
        user_prompt=build_screening_council_red_user_prompt(
            theme=theme,
            market=market,
            desired_count=desired_count,
            candidates=candidates,
            bull_round=bull_round,
        ),
        max_results=7,
        max_fetches=10,
        verbose=verbose,
    )
    if verbose:
        print("[screen] council round 3: reconsideration")
    reconsideration_round = safe_run_agent_with_tools(
        client=client,
        name="screening_council_reconsideration",
        model=model,
        think=think,
        timeout_seconds=timeout_seconds,
        system_prompt=build_screening_council_reconsider_prompt(),
        user_prompt=build_screening_council_reconsider_user_prompt(
            theme=theme,
            market=market,
            desired_count=desired_count,
            candidates=candidates,
            bull_round=bull_round,
            red_round=red_round,
        ),
        max_results=7,
        max_fetches=10,
        verbose=verbose,
    )
    prompt = build_second_screen_prompt(
        theme=theme,
        market=market,
        desired_count=desired_count,
        candidates=candidates,
        bull_round=bull_round.content,
        red_round=red_round.content,
        reconsideration_round=reconsideration_round.content,
    )
    fallback = {
        "recommended": sorted(candidates, key=screen_sort_key, reverse=True)[:desired_count],
        "committee_notes": {
            "bull_round": bull_round.content,
            "red_round": red_round.content,
            "reconsideration_round": reconsideration_round.content,
        },
    }
    try:
        if verbose:
            print("[screen] council final chair synthesis")
        response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are the chair of a disciplined multi-stage stock screening council. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            think=resolve_think(model, think),
            format="json",
        )
        parsed, _ = parse_structured_response(response.message.content or "")
        if isinstance(parsed, dict):
            parsed.setdefault(
                "committee_notes",
                {
                    "bull_round": bull_round.content,
                    "red_round": red_round.content,
                    "reconsideration_round": reconsideration_round.content,
                },
            )
            if verbose:
                print("[screen] council final chair completed")
            return parsed
    except Exception:
        pass
    if verbose:
        print("[screen] council fell back to ranked shortlist")
    return fallback


def run_screening_diligence(
    *,
    client: Client,
    model: str,
    think: str,
    timeout_seconds: float,
    theme: str,
    market: str,
    candidate: dict[str, Any],
    max_results: int,
    max_fetches: int,
    verbose: bool = False,
) -> dict[str, Any]:
    note = safe_run_agent_with_tools(
        client=client,
        name="screening_diligence",
        model=model,
        think=think,
        timeout_seconds=timeout_seconds,
        system_prompt=build_screening_diligence_prompt(max_results=max_results, max_fetches=max_fetches),
        user_prompt=build_screening_diligence_user_prompt(theme=theme, market=market, candidate=candidate),
        max_results=max_results,
        max_fetches=max_fetches,
        verbose=verbose,
    )
    evidence = extract_evidence_from_traces([note.tool_traces])[:6]
    return enrich_screen_candidate(candidate=candidate, note=note.content, evidence=evidence, theme=theme, market=market)


def enrich_screen_candidate(
    *,
    candidate: dict[str, Any],
    note: str,
    evidence: list[dict[str, str]],
    theme: str,
    market: str,
) -> dict[str, Any]:
    vertical_summary = preferred_section_text(
        extract_markdown_sections(note, "业务与主题契合度", "纵向调查", "公司质量", "经营与客户"),
        "\n".join(evidence_signal_lines([{"tool_name": "digest", "arguments": {}, "result": {"results": evidence}}])[:3]),
    ) or clean_research_summary(candidate.get("rationale", ""))
    horizontal_summary = preferred_section_text(
        extract_markdown_sections(note, "横向对比", "可比公司", "估值锚", "为什么值得继续研究"),
        clean_research_summary(candidate.get("rationale", "")),
    ) or clean_research_summary(candidate.get("rationale", ""))
    why_now = preferred_section_text(
        extract_markdown_sections(note, "为什么现在值得看", "Why now"),
        clean_research_summary(candidate.get("rationale", "")),
    ) or clean_research_summary(candidate.get("rationale", ""))
    why_not_now = preferred_section_text(
        extract_markdown_sections(note, "为什么现在还不能下重注", "Why not now", "主要断点"),
        "仍需继续核实关键经营与估值假设。",
    )
    exclusion_reason = clip_text(
        why_not_now or "当前主题纯度、证据质量或 why-now 还不足以进入完整精筛。",
        220,
    )
    avg_quality = 0
    if evidence:
        avg_quality = round(sum(int(item.get("quality") or 0) for item in evidence) / len(evidence))
    resolved_company_name, resolved_ticker = derive_company_identity(
        market=market,
        candidate=candidate,
        evidence=evidence,
        note=note,
    )
    upgraded_score = min(
        98,
        max(
            int(candidate.get("screen_score") or 50),
            int(candidate.get("screen_score") or 50) + min(8, len(evidence)) + max(0, (avg_quality - 60) // 8),
        ),
    )
    enriched = normalize_screen_candidates([candidate], theme=theme, market=market)[0]
    enriched.update(
        {
            "company_name": resolved_company_name or enriched.get("company_name") or candidate.get("company_name") or "",
            "ticker": resolved_ticker or enriched.get("ticker") or candidate.get("ticker") or "",
            "screen_score": upgraded_score,
            "source_count": max(int(candidate.get("source_count") or 1), len(evidence)),
            "vertical_summary": clip_text(vertical_summary, 600),
            "horizontal_summary": clip_text(horizontal_summary, 600),
            "why_now": clip_text(why_now, 280),
            "why_not_now": clip_text(why_not_now, 280),
            "exclusion_reason": exclusion_reason,
            "evidence_snapshot": evidence,
            "diligence_note": clip_text(clean_research_summary(note), 1200),
            "rationale": clip_text(why_now or clean_research_summary(candidate.get("rationale", "")), 320),
        }
    )
    return enriched


def merge_screen_candidates(candidates: list[dict[str, Any]], *, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reference_map = {
        slugify(item.get("ticker") or item.get("company_name") or ""): item
        for item in references
    }
    merged: list[dict[str, Any]] = []
    for item in candidates:
        identifier = slugify(item.get("ticker") or item.get("company_name") or "")
        reference = reference_map.get(identifier) or {}
        combined = {**reference, **item}
        combined["company_name"] = choose_preferred_company_name(
            str(reference.get("company_name") or ""),
            str(item.get("company_name") or ""),
            ticker=str(combined.get("ticker") or reference.get("ticker") or item.get("ticker") or ""),
        )
        for key in ("vertical_summary", "horizontal_summary", "why_now", "why_not_now", "evidence_snapshot", "diligence_note"):
            if key not in combined and key in reference:
                combined[key] = reference[key]
        if not combined.get("rationale"):
            combined["rationale"] = reference.get("rationale", "")
        merged.append(combined)
    merged.sort(key=screen_sort_key, reverse=True)
    return merged


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
        primary_document_path = str(
            artifact.get("primary_document_path")
            or artifact.get("zh_docx_path")
            or artifact.get("en_docx_path")
            or ""
        )
        entry["last_report_path"] = primary_document_path
        entry["next_run_at"] = (now.timestamp() + int(entry.get("interval_hours", 24)) * 3600)
        entry["next_run_at"] = datetime.fromtimestamp(entry["next_run_at"], UTC).isoformat()
        artifacts.append(
            {
                "identifier": entry["identifier"],
                "zh_docx_path": str(artifact.get("zh_docx_path") or primary_document_path),
                "en_docx_path": str(artifact.get("en_docx_path") or ""),
                "primary_document_path": primary_document_path,
                "verdict": (artifact.get("payload") or {}).get("verdict", "watchlist"),
                "quick_take": (artifact.get("payload") or {}).get("quick_take", ""),
                "target_snapshot": format_target_price_snapshot((artifact.get("payload") or {}).get("target_prices") or {}),
            }
        )
    save_watchlist(paths, entries)
    zh_digest_path = ""
    en_digest_path = ""
    if artifacts:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        digest_paths = build_watchlist_digest_document_paths(
            digests_dir=paths.digests_dir,
            timestamp=timestamp,
            single_document=paths.single_document_delivery,
        )
        if paths.single_document_delivery:
            write_bilingual_watchlist_digest_docx(digest_paths["primary"], artifacts=artifacts)
        else:
            write_watchlist_digest_docx(digest_paths["zh"], artifacts=artifacts, language="zh")
            write_watchlist_digest_docx(digest_paths["en"], artifacts=artifacts, language="en")
        zh_digest_path = str(digest_paths["zh"])
        en_digest_path = str(digest_paths["en"])
    return {
        "processed": processed,
        "artifacts": artifacts,
        "zh_digest_path": zh_digest_path,
        "en_digest_path": en_digest_path,
        "digest_path": zh_digest_path,
    }


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
    mode = desk_briefing_mode()
    title = "Weekly Watchlist Wrap" if mode == "weekly" else "Morning Watchlist Brief"
    top_name = artifacts[0]["identifier"] if artifacts else "n/a"
    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{datetime.now(UTC).isoformat()}`",
        f"- Refreshed names: `{len(artifacts)}`",
        "",
    ]
    if artifacts:
        lines.extend(
            [
                "## Desk Summary",
                f"- Highest-priority refresh: `{top_name}`",
                f"- Lead verdict: `{artifacts[0].get('verdict', 'watchlist')}`",
                f"- Lead target snapshot: {artifacts[0].get('target_snapshot', 'n/a')}",
                "",
            ]
        )
    for item in artifacts:
        lines.extend(
            [
                f"## {item['identifier']}",
                f"- Verdict: `{item.get('verdict', 'watchlist')}`",
                f"- Quick take: {item.get('quick_take', '') or 'n/a'}",
                f"- Target snapshot: {item.get('target_snapshot', '') or 'n/a'}",
                f"- Report: `{item.get('primary_document_path', '') or item.get('zh_docx_path', '')}`",
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
        body = render_email_research_reply(payload, artifact["primary_document_path"])
        return {"body": body, "attachments": unique_attachment_paths(artifact["primary_document_path"])}
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
        body = render_email_screen_reply(theme=command["theme"], payload=artifact["payload"], document_path=artifact["primary_document_path"])
        attachments = unique_attachment_paths(artifact["primary_document_path"], *artifact.get("report_paths", []))
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
        body = render_email_watchlist_roster_reply(entries)
        return {"body": body, "attachments": []}
    if kind == "watchlist_run_due":
        result = run_due_watchlist(paths=paths, config=config, limit=10, verbose=verbose)
        body = render_email_watchlist_digest_reply(result)
        attachments = unique_attachment_paths(result.get("digest_path"), *(item["primary_document_path"] for item in result["artifacts"]))
        return {"body": body, "attachments": attachments}
    raise RuntimeError(f"Unsupported email command: {kind}")


def render_email_research_reply(payload: dict[str, Any], document_path: str) -> str:
    targets = payload.get("target_prices") or {}
    bull_case = list(payload.get("bull_case") or [])
    risks = list(payload.get("risks") or [])
    lines = [
        "# Single-Name Desk Note",
        "",
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
    lines.extend(["", "Desk action:", f"- Attached memo document: {document_path}"])
    return "\n".join(lines)


def render_email_screen_reply(*, theme: str, payload: dict[str, Any], document_path: str) -> str:
    finalists = payload.get("finalists") or []
    initial_candidates = payload.get("initial_candidates") or []
    stage_one_candidates = payload.get("stage_one_candidates") or []
    lines = [
        "# Screening Brief",
        "",
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
                f"   targets: {format_target_price_snapshot(report_payload.get('target_prices') or {})}",
            ]
        )
    lines.extend(["", "Desk action:", f"- Attached screening summary document: {document_path}"])
    return "\n".join(lines)


def desk_briefing_mode(now: datetime | None = None) -> str:
    reference = now or datetime.now(UTC)
    return "weekly" if reference.weekday() == 0 else "morning"


def format_target_price_snapshot(targets: dict[str, Any]) -> str:
    if not targets:
        return "n/a"
    chunks: list[str] = []
    for key, label in (("short_term", "ST"), ("medium_term", "MT"), ("long_term", "LT")):
        item = targets.get(key) or {}
        if item.get("price"):
            chunks.append(f"{label} {item.get('price')} ({item.get('horizon', 'n/a')})")
    return " | ".join(chunks) if chunks else "n/a"


def render_email_watchlist_roster_reply(entries: list[dict[str, Any]]) -> str:
    heading = "# Weekly Coverage Roster" if desk_briefing_mode() == "weekly" else "# Morning Coverage Roster"
    if not entries:
        return "\n".join([heading, "", "Current watchlist is empty."])
    lines = [
        heading,
        "",
        f"- Coverage names: {len(entries)}",
        "",
        "Priority queue:",
    ]
    for entry in sorted(entries, key=lambda item: item.get("next_run_at", ""))[:12]:
        label = entry.get("ticker") or entry.get("stock_name")
        lines.append(
            f"- {label} | cadence={entry.get('interval_spec')} | next={entry.get('next_run_at')} | last={entry.get('last_run_at') or 'never'}"
        )
    return "\n".join(lines)


def render_email_watchlist_digest_reply(result: dict[str, Any]) -> str:
    artifacts = result.get("artifacts") or []
    heading = "# Weekly Watchlist Wrap" if desk_briefing_mode() == "weekly" else "# Morning Watchlist Brief"
    lines = [
        heading,
        "",
        f"- Refreshed names: {result.get('processed', 0)}",
    ]
    if result.get("zh_digest_path") or result.get("en_digest_path"):
        lines.append(f"- Attached digest bundle: {result.get('zh_digest_path') or result.get('en_digest_path')}")
    lines.extend(["", "Desk highlights:"])
    if not artifacts:
        lines.append("- No watchlist names were due in this cycle.")
        return "\n".join(lines)
    for item in artifacts[:8]:
        lines.extend(
            [
                f"- {item['identifier']}",
                f"  verdict={item.get('verdict', 'watchlist')} | {item.get('target_snapshot', 'n/a')}",
                f"  quick_take={item.get('quick_take', '') or 'n/a'}",
            ]
        )
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
        if path.suffix == ".json":
            maintype, subtype = "application", "json"
        elif path.suffix == ".docx":
            maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif path.suffix == ".md":
            maintype, subtype = "text", "markdown"
        else:
            maintype, subtype = "application", "octet-stream"
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
        "先做 sector-specific query planning：根据板块特征主动设计多路查询，既查纯正标的，也查邻近赛道和可比公司。"
        "如果主题稀疏，不要停在泛泛概念文章上，要继续追问哪个名字是真正上市、真正可交易、真正有产品或商业化牵引。"
    )


def build_screening_user_prompt(*, theme: str, desired_count: int, market: str, seed_tickers: list[str]) -> str:
    sector_profile = sector_profile_for(theme, market)
    payload = {
        "theme": theme,
        "desired_count": desired_count,
        "market": market,
        "seed_tickers": seed_tickers,
        "sector_profile": sector_profile,
        "goal": "先进行初筛，找出真正值得进入二筛和精筛的股票候选。",
    }
    market_guard = "如果 market=US，只能保留在美国上市或主要在美股交易的公司，禁止把 A 股、港股或私有公司混进候选池。"
    return f"{market_guard} 请围绕这个板块方向去主动联网搜索并寻找股票候选：{json.dumps(payload, ensure_ascii=False)}"


def build_screening_densification_user_prompt(
    *,
    theme: str,
    desired_count: int,
    market: str,
    seed_tickers: list[str],
    existing_candidates: list[dict[str, Any]],
) -> str:
    sector_profile = sector_profile_for(theme, market)
    payload = {
        "theme": theme,
        "desired_count": desired_count,
        "market": market,
        "seed_tickers": seed_tickers,
        "sector_profile": sector_profile,
        "existing_candidates": existing_candidates,
        "goal": "候选池仍然太稀，需要继续联网扩大覆盖面，优先寻找公开交易、主题相关、且能确认 ticker 的标的。",
    }
    return (
        "继续进行第二轮 theme scout。"
        "不要重复已有候选。"
        "优先挖掘公开上市纯度更高或更值得继续研究的名字；如果纯正标的很少，可以补充关键设备、核心上游、神经调控/脑机接口邻近基础设施公司。 "
        "如果 market=US，必须明确 ticker，并尽量确认是 NASDAQ/NYSE/AMEX/OTC 上可交易的名字。 "
        f"输入：{json.dumps(payload, ensure_ascii=False)}"
    )


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
        "If market=US, candidates must be tradable US-listed names with US-style tickers, not mainland China A-shares, Hong Kong listings, or private companies. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def build_screening_densification_synthesis_prompt(
    *,
    theme: str,
    desired_count: int,
    market: str,
    evidence: list[dict[str, str]],
    seed_tickers: list[str],
    existing_candidates: list[dict[str, Any]],
) -> str:
    payload = {
        "theme": theme,
        "desired_count": desired_count,
        "market": market,
        "seed_tickers": seed_tickers,
        "existing_candidates": existing_candidates,
        "evidence": evidence,
    }
    return (
        "Return JSON only with a top-level `candidates` array. "
        "This is a densification pass, so prioritize adding missing, distinct, listed names rather than repeating existing ones. "
        "Each candidate must contain: company_name, ticker, market, rationale, screen_score, confidence, source_count, angle. "
        "Prefer explicit ticker confirmation from exchange pages, investor relations pages, or reputable financial coverage. "
        "If market=US, tickers must look like US tradable symbols and companies should be publicly listed in the US or OTC market. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def build_screening_council_bull_prompt() -> str:
    return (
        "你是二筛委员会里的支持派主席，由 Peter Lynch、Rakesh Jhunjhunwala 和 Stanley Druckenmiller 的风格蒸馏而来。"
        "你的任务不是盲目乐观，而是为真正值得进入昂贵精筛的标的建立最强支持论证。"
        "你可以继续联网搜索，补强业务契合度、产业催化剂、交易窗口、可比优势和 why-now 论据。"
        "输出中文 Markdown，结构固定为：支持派名单、每个候选的 why-now、横向优势、最值得继续研究的原因、需要红队重点质疑的断点。"
    )


def build_screening_council_user_prompt(
    *,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "candidates": candidates,
        "goal": "先站在支持派角度，筛出最值得进入精筛的候选，并把 why-now 说硬。",
    }
    return f"请启动二筛议会第一轮支持派讨论：{json.dumps(payload, ensure_ascii=False)}"


def build_screening_council_red_prompt() -> str:
    return (
        "你是二筛委员会里的红队主席，由 Michael Burry、Taleb 和 Ackman 的风格蒸馏而来。"
        "你的任务是系统性拆解支持派的论点，寻找主题错配、证据污染、估值幻觉、客户集中、周期错判和'为什么不是别的股票'这类硬问题。"
        "你可以继续联网搜索并做交叉核验。"
        "输出中文 Markdown，结构固定为：核心反对意见、逐个候选的主要漏洞、最危险的假设、应当降级或淘汰的名字、仍可保留但必须附带的保留意见。"
    )


def build_screening_council_red_user_prompt(
    *,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
    bull_round: AgentRunResult,
) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "candidates": candidates,
        "bull_round": bull_round.content,
        "goal": "拆解支持派论点，逼出最危险的主题错配、估值幻觉和证据质量问题。",
    }
    return f"请启动二筛议会第二轮红队质询：{json.dumps(payload, ensure_ascii=False)}"


def build_screening_council_reconsider_prompt() -> str:
    return (
        "你是二筛委员会里的复议主席，由 Howard Marks、Charlie Munger 和 Nick Sleep 的风格蒸馏而来。"
        "你要在支持派与红队之后重新审视候选，不追求热闹，而追求代价昂贵的深研资源应该投到哪里。"
        "你可以继续联网搜索，但重点是裁决：哪些名字值得继续，哪些只能保留观察，哪些应直接淘汰。"
        "输出中文 Markdown，结构固定为：复议结论、保留名单、降级名单、仍未解决的断点、进入最终主席团裁决前必须记住的原则。"
    )


def build_screening_council_reconsider_user_prompt(
    *,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
    bull_round: AgentRunResult,
    red_round: AgentRunResult,
) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "candidates": candidates,
        "bull_round": bull_round.content,
        "red_round": red_round.content,
        "goal": "在支持派和红队之后做复议，判断谁还能进入昂贵的完整精筛。",
    }
    return f"请启动二筛议会第三轮复议：{json.dumps(payload, ensure_ascii=False)}"


def build_second_screen_prompt(
    *,
    theme: str,
    market: str,
    desired_count: int,
    candidates: list[dict[str, Any]],
    bull_round: str,
    red_round: str,
    reconsideration_round: str,
) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "desired_count": desired_count,
        "candidates": candidates,
        "bull_round": bull_round,
        "red_round": red_round,
        "reconsideration_round": reconsideration_round,
    }
    return (
        "Return JSON only with top-level keys `recommended` and `committee_notes`. "
        "`recommended` must be an array. `committee_notes` must be an object with keys `bull_round`, `red_round`, and `reconsideration_round`. "
        "Select the few names most worth full deep-research work after multi-stage vertical and horizontal investigation, red-team dissent, and reconsideration. "
        "Each recommended item must contain: company_name, ticker, market, rationale, screen_score, confidence, angle, why_now, why_not_now. "
        "Favor names with cleaner business linkage, stronger evidence quality, better peer-relative upside, and clearer why-now framing. "
        "Penalize vague theme adjacency, poor source quality, and unresolved core contradictions. "
        "The final chair decision should reflect all three rounds instead of blindly following the initial support case. "
        f"Input: {json.dumps(payload, ensure_ascii=False)}"
    )


def build_screening_diligence_prompt(*, max_results: int, max_fetches: int) -> str:
    return (
        "你是 buy-side screening desk 的尽调分析师。"
        "初筛不是简单搜名字，而是要对每个候选做一轮联网 mini-dossier。"
        f"Use no more than {max_results} search results per search and no more than {max_fetches} page fetches total. "
        "必须同时完成横向和纵向调查。纵向包括业务与主题契合度、客户/订单/经营信号、关键风险。"
        "横向包括可比公司、估值锚、为什么它比别的候选更值得继续研究。"
        "优先搜索公司官网、交易所、公告、年报、投资者关系页、权威财经媒体。"
        "输出中文 Markdown，包含：业务与主题契合度、纵向调查、横向对比、为什么现在值得看、为什么现在还不能下重注、继续研究建议。"
    )


def build_screening_diligence_user_prompt(*, theme: str, market: str, candidate: dict[str, Any]) -> str:
    payload = {
        "theme": theme,
        "market": market,
        "candidate": {
            "company_name": candidate.get("company_name"),
            "ticker": candidate.get("ticker"),
            "market": candidate.get("market") or market,
            "seed_rationale": candidate.get("rationale"),
            "seed_score": candidate.get("screen_score"),
        },
        "goal": "做一轮严格的联网初筛尽调，判断这只股票是不是应该进入昂贵的完整深研流程。",
    }
    return f"请围绕这个候选标的做 mini-dossier：{json.dumps(payload, ensure_ascii=False)}"


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
        why_now = str(item.get("why_now") or item.get("stage_two_note") or item.get("rationale") or "").strip()
        why_not_now = str(item.get("why_not_now") or "").strip()
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
                f"- Why not now: {why_not_now or '主要断点仍需继续通过完整深研验证。'}",
                f"- Quick take: {quick_take or '待补充'}",
                f"- Vertical summary: {item.get('vertical_summary', '') or '待补充'}",
                f"- Horizontal summary: {item.get('horizontal_summary', '') or '待补充'}",
                f"- Short-term target: {short_term.get('price', 'n/a')} | {short_term.get('horizon', 'n/a')}",
                f"- Bull/Bear focus: {summarize_bull_bear(payload)}",
                f"- Report path: `{item.get('primary_document_path', '') or item.get('zh_docx_path', '')}`",
            ]
        )

    def rejected_bucket(items: list[dict[str, Any]]) -> str:
        rejected = [item for item in items if slugify(item.get("ticker") or item.get("company_name") or "") not in {
            slugify(finalist.get("ticker") or finalist.get("company_name") or "") for finalist in finalists
        }]
        if not rejected:
            return "- No clear rejects from the second-screen pool."
        return "\n".join(
            f"- `{item.get('ticker') or item.get('company_name')}` | score={item.get('screen_score')} | not promoted because: {item.get('exclusion_reason') or item.get('why_not_now') or item.get('rationale', 'research upside was weaker')}"
            for item in rejected[:6]
        )

    stage_one_block = "\n".join(
        "\n".join(
            [
                f"- `{item.get('ticker') or item.get('company_name')}` | score={item.get('screen_score')} | why_now={item.get('why_now') or item.get('rationale', '')}",
                f"  vertical={item.get('vertical_summary', '') or 'n/a'}",
                f"  horizontal={item.get('horizontal_summary', '') or 'n/a'}",
                f"  why_not_now={item.get('why_not_now', '') or 'n/a'}",
            ]
        )
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
        f"本轮围绕 `{theme}` 先做公开网页 scout，然后对入池候选逐个做联网 mini-dossier，再做二筛委员会压缩，最后对最值得投入时间的标的做完整多 agent 深研。"
        f" 当前最优先继续跟的名字是 `{top.get('company_name')}`，因为它在 why-now、横向对比、纵向尽调和最终 memo 一致性上最稳。"
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
    timeout_seconds: float,
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
        response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
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
        response = chat_with_guard(
            client,
            timeout_seconds=config.timeout_seconds,
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


def load_cross_validated_fallback() -> tuple[Any, Any]:
    if not CROSS_VALIDATED_SEARCH_ROOT.exists():
        raise RuntimeError(f"cross-validated-search repo not found at {CROSS_VALIDATED_SEARCH_ROOT}")
    root = str(CROSS_VALIDATED_SEARCH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from cross_validated_search.browse_page import browse  # type: ignore
    from cross_validated_search.core import UltimateSearcher  # type: ignore

    return UltimateSearcher, browse


def market_region(market: str) -> str:
    normalized = (market or "").upper()
    if normalized == "US":
        return "en-us"
    if normalized in {"CN", "HK"}:
        return "zh-cn"
    return "wt-wt"


def fallback_search_with_cross_validated(*, query: str, max_results: int, market: str) -> dict[str, Any]:
    UltimateSearcher, _ = load_cross_validated_fallback()
    answer = UltimateSearcher().search(
        query,
        region=market_region(market),
        providers=["ddgs"],
    )
    results: list[dict[str, str]] = []
    for source in list(getattr(answer, "sources", []) or [])[:max_results]:
        results.append(
            {
                "title": str(getattr(source, "title", "") or "Untitled source").strip(),
                "url": str(getattr(source, "url", "") or "").strip(),
                "content": str(
                    getattr(source, "snippet", "")
                    or getattr(source, "summary", "")
                    or getattr(source, "extra", "")
                    or ""
                ).strip(),
            }
        )
    return {"results": results, "fallback": "cross-validated-search"}


def fallback_fetch_with_cross_validated(*, url: str) -> dict[str, Any]:
    _, browse = load_cross_validated_fallback()
    result = browse(url, max_chars=12000)
    if result.get("status") == "success":
        content = str(result.get("content") or "").strip()
        return {
            "url": url,
            "title": str(result.get("title") or url).strip(),
            "content": content,
            "excerpt": clip_text(content, 420),
            "fallback": "cross-validated-search",
        }
    return {"url": url, "error": str(result.get("error") or "cross-validated fetch failed"), "fallback": "cross-validated-search"}


def perform_search_with_fallback(*, client: Client, query: str, max_results: int, market: str) -> dict[str, Any]:
    try:
        result = client.web_search(query=query, max_results=max_results).model_dump()
        if isinstance(result, dict) and result.get("error"):
            fallback = fallback_search_with_cross_validated(query=query, max_results=max_results, market=market)
            fallback["primary_error"] = str(result.get("error"))
            return fallback
        return result
    except Exception as exc:
        fallback = fallback_search_with_cross_validated(query=query, max_results=max_results, market=market)
        fallback["primary_error"] = str(exc)
        return fallback


def perform_fetch_with_fallback(*, client: Client, url: str) -> dict[str, Any]:
    try:
        result = client.web_fetch(url=url).model_dump()
        if isinstance(result, dict) and result.get("error"):
            fallback = fallback_fetch_with_cross_validated(url=url)
            fallback["primary_error"] = str(result.get("error"))
            return fallback
        return result
    except Exception as exc:
        fallback = fallback_fetch_with_cross_validated(url=url)
        fallback["primary_error"] = str(exc)
        return fallback


def chat_with_guard(
    client: Client,
    *,
    timeout_seconds: float,
    **kwargs: Any,
) -> Any:
    return client.chat(**kwargs)


def call_with_guard(
    func: Any,
    *,
    timeout_seconds: float,
    **kwargs: Any,
) -> Any:
    return func(**kwargs)


def payload_contains_cjk(value: Any) -> bool:
    if isinstance(value, str):
        return contains_cjk(value)
    if isinstance(value, list):
        return any(payload_contains_cjk(item) for item in value)
    if isinstance(value, dict):
        return any(payload_contains_cjk(item) for item in value.values())
    return False


def translate_structured_payload(
    client: Client,
    *,
    model: str,
    think: str,
    timeout_seconds: float,
    payload: dict[str, Any],
    task_label: str,
    fallback_payload: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "Translate the following JSON payload into English-only JSON.\n"
        "Return JSON only.\n"
        "Keep the same keys and nested structure.\n"
        "Preserve numbers, tickers, horizons, URLs, and proper nouns when they are already in English.\n"
        "Do not leave Chinese text in the output.\n"
        f"Task: {task_label}\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial research translator. Return strict JSON only. Translate all natural-language values into fluent English while preserving the schema exactly.",
                },
                {"role": "user", "content": prompt},
            ],
            think=resolve_think(model, think),
        )
        content = response.message.content or ""
        parsed, _ = parse_structured_response(content)
        if isinstance(parsed, dict) and not payload_contains_cjk(parsed):
            return parsed
    except Exception:
        pass
    return fallback_payload


def build_report_document_paths(*, reports_dir: Path, timestamp: str, slug: str, single_document: bool = False) -> dict[str, Path]:
    if single_document:
        primary = reports_dir / f"{timestamp}-{slug}.docx"
        return {"primary": primary, "zh": primary, "en": primary}
    zh = reports_dir / f"{timestamp}-{slug}-zh.docx"
    en = reports_dir / f"{timestamp}-{slug}-en.docx"
    return {"primary": zh, "zh": zh, "en": en}


def build_screening_document_paths(*, screens_dir: Path, timestamp: str, slug: str, single_document: bool = False) -> dict[str, Path]:
    if single_document:
        primary = screens_dir / f"{timestamp}-{slug}.docx"
        return {"primary": primary, "zh": primary, "en": primary}
    zh = screens_dir / f"{timestamp}-{slug}-zh.docx"
    en = screens_dir / f"{timestamp}-{slug}-en.docx"
    return {"primary": zh, "zh": zh, "en": en}


def build_watchlist_digest_document_paths(*, digests_dir: Path, timestamp: str, single_document: bool = False) -> dict[str, Path]:
    if single_document:
        primary = digests_dir / f"{timestamp}-watchlist-digest.docx"
        return {"primary": primary, "zh": primary, "en": primary}
    zh = digests_dir / f"{timestamp}-watchlist-digest-zh.docx"
    en = digests_dir / f"{timestamp}-watchlist-digest-en.docx"
    return {"primary": zh, "zh": zh, "en": en}


def build_machine_artifact_path(*, artifacts_dir: Path, category: str, filename: str) -> Path:
    target_dir = artifacts_dir / category
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename


def unique_attachment_paths(*paths: str | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in paths:
        candidate = str(item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


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
    timeout_seconds: float,
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
    planning_response = chat_with_guard(
        client,
        timeout_seconds=timeout_seconds,
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
            result = call_with_guard(client.web_search, timeout_seconds=timeout_seconds, **arguments).model_dump()
        elif tool_name == "web_fetch":
            if fetch_count >= max_fetches:
                result = {"error": "fetch budget exhausted"}
            else:
                result = call_with_guard(client.web_fetch, timeout_seconds=timeout_seconds, **arguments).model_dump()
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
        synthesis_response = chat_with_guard(
            client,
            timeout_seconds=timeout_seconds,
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


def looks_like_us_ticker(value: str) -> bool:
    text = value.strip().upper()
    return bool(re.fullmatch(r"[A-Z]{1,5}", text))


def candidate_name_needs_cleanup(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    if "|" in text or len(text) > 48:
        return True
    return any(f" {verb} " in f" {text} " for verb in COMPANY_ACTION_VERBS)


def choose_preferred_company_name(*values: str, ticker: str = "") -> str:
    cleaned: list[str] = []
    for value in values:
        text = clean_company_name(value)
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return ticker.strip().upper()
    ranked = sorted(
        cleaned,
        key=lambda item: (
            candidate_name_needs_cleanup(item),
            item.strip().upper() == ticker.strip().upper(),
            len(item),
        ),
    )
    return ranked[0]


def clean_company_name(value: str) -> str:
    text = sanitize_source_text(value)
    text = re.split(r"[|:–—]", text, maxsplit=1)[0].strip()
    verb_pattern = "|".join(re.escape(item) for item in COMPANY_ACTION_VERBS)
    match = re.match(rf"(.+?)\s+(?:{verb_pattern})\b", text)
    if match:
        text = match.group(1).strip()
    for phrase in TITLE_NOISE_PHRASES:
        text = re.sub(rf"\b{re.escape(phrase)}\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\b(?:NASDAQ|NYSE|AMEX|OTCQX|OTCQB|OTC)\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s{2,}", " ", text).strip(" -|:")
    return text


def extract_identity_hints(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    company_token = r"[A-Z][A-Za-z0-9&',./-]+"
    company_phrase = rf"{company_token}(?:\s+{company_token}){{0,7}}"
    patterns = [
        re.compile(
            rf"({company_phrase})\s*\((?:NASDAQ|NYSE|AMEX|OTCQX|OTCQB|OTC)[:\s-]*([A-Z]{{1,5}})\)",
            re.IGNORECASE,
        ),
        re.compile(
            rf"({company_phrase}).{{0,40}}US OTCQX[:\s-]*([A-Z]{{1,5}})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"({company_phrase})\s*[-|:]\s*(?:NASDAQ|NYSE|AMEX|OTCQX|OTCQB|OTC)[:\s-]*([A-Z]{{1,5}})",
            re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            company = clean_company_name(match.group(1))
            ticker = match.group(2).upper().strip()
            if company and looks_like_us_ticker(ticker):
                candidates.append((company, ticker))
    return candidates


def derive_company_identity(*, market: str, candidate: dict[str, Any], evidence: list[dict[str, str]], note: str = "") -> tuple[str, str]:
    current_name = clean_company_name(str(candidate.get("company_name") or ""))
    current_ticker = normalize_ticker(str(candidate.get("ticker") or ""), "", market) if candidate.get("ticker") else ""
    texts: list[str] = [current_name, note]
    for item in evidence:
        texts.append(str(item.get("title") or ""))
        texts.append(str(item.get("claim") or ""))
        texts.append(str(item.get("excerpt") or ""))
    identity_counts: dict[tuple[str, str], int] = {}
    for text in texts:
        for company, ticker in extract_identity_hints(text):
            identity_counts[(company, ticker)] = identity_counts.get((company, ticker), 0) + 1
    if identity_counts:
        ticker_counts: dict[str, int] = {}
        ticker_company_names: dict[str, list[str]] = {}
        for (company, ticker), count in identity_counts.items():
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + count
            ticker_company_names.setdefault(ticker, []).append(company)
        best_ticker = max(ticker_counts.items(), key=lambda entry: (entry[1], len(entry[0])))[0]
        best_company = choose_preferred_company_name(
            current_name,
            *ticker_company_names.get(best_ticker, []),
            ticker=best_ticker,
        )
        return best_company, best_ticker
    if market.upper() == "US":
        return choose_preferred_company_name(current_name, ticker=current_ticker), current_ticker
    return current_name or current_ticker, current_ticker


def default_sector_query_axes(theme: str, market: str) -> list[str]:
    market_label = "US-listed" if market.upper() == "US" else f"{market.upper()} listed"
    return [
        f"{market_label} {theme} companies",
        f"public companies with {theme} exposure",
        f"{theme} pure-play vs adjacent infrastructure public names",
        f"{theme} customer traction backlog commercialization public companies",
        f"{theme} listed peers valuation milestones and competitive positioning",
    ]


def sector_profile_for(theme: str, market: str) -> dict[str, Any]:
    normalized = theme.strip().lower()
    for profile in SECTOR_PROFILES:
        if any(token in normalized for token in profile["match_tokens"]):
            anchors = [dict(item) for item in profile.get("anchors", ()) if item["market"] == market.upper()]
            public_labels = [f"{item['company_name']} ({item['ticker']})" for item in anchors]
            return {
                "sector": profile["sector"],
                "keywords": list(profile["keywords"]),
                "query_axes": list(profile["query_axes"]),
                "listed_anchor_names": public_labels,
                "non_public_reference_names": list(profile["non_public_reference_names"]),
                "focus_questions": list(profile["focus_questions"]),
            }
    return {
        "sector": theme,
        "keywords": [theme],
        "query_axes": default_sector_query_axes(theme, market),
        "listed_anchor_names": [],
        "non_public_reference_names": [],
        "focus_questions": [
            "which names are truly public and tradable in the target market",
            "which names are pure-play exposure versus broad narrative adjacency",
            "which companies have the clearest commercialization, customer, or regulatory milestones",
        ],
    }


def is_market_compatible_candidate(*, market: str, ticker: str, company_name: str, market_hint: str) -> bool:
    normalized_market = market.upper().strip()
    ticker_text = ticker.strip().upper()
    company_text = company_name.strip()
    hint_text = market_hint.upper().strip()
    if normalized_market == "US":
        if not looks_like_us_ticker(ticker_text):
            return False
        if any(token in ticker_text for token in [".SH", ".SZ", ".HK"]):
            return False
        if hint_text and hint_text not in US_LISTING_HINTS:
            return False
        if re.search(r"[\u4e00-\u9fff]", company_text) and not re.search(r"[A-Z]", company_text):
            return False
    if normalized_market == "CN":
        if ticker_text and not bool(re.fullmatch(r"\d{6}(?:\.(?:SH|SZ))?", ticker_text)):
            return False
    return True


def build_seed_candidates(*, seed_tickers: list[str], theme: str, market: str) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for raw in seed_tickers:
        ticker = normalize_ticker(raw, "", market)
        if not ticker:
            continue
        if not is_market_compatible_candidate(market=market, ticker=ticker, company_name=ticker, market_hint=market):
            continue
        seeds.append(
            {
                "company_name": ticker,
                "ticker": ticker,
                "market": market,
                "rationale": f"用户提供的种子标的 `{ticker}`，与 `{theme}` 主题直接相关，必须进入候选池核验。",
                "screen_score": 88,
                "confidence": "medium",
                "source_count": 1,
                "angle": theme,
                "why_now": f"种子标的 `{ticker}` 需要经过完整联网核验，判断其是否应进入完整精筛。",
                "why_not_now": "当前仅为种子入口，尚未完成深度证据核验。",
            }
        )
    return seeds


def merge_seed_candidates(*, candidates: list[dict[str, Any]], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not seeds:
        return candidates
    combined = [*candidates]
    existing = {slugify(item.get("ticker") or item.get("company_name") or "") for item in candidates}
    for seed in seeds:
        identifier = slugify(seed.get("ticker") or seed.get("company_name") or "")
        if identifier not in existing:
            combined.append(seed)
    merged = merge_screen_candidates(combined, references=seeds)
    merged.sort(key=screen_sort_key, reverse=True)
    return merged


def combine_candidate_lists(*candidate_lists: list[dict[str, Any]], theme: str, market: str) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    for candidate_list in candidate_lists:
        for item in normalize_screen_candidates(candidate_list, theme=theme, market=market):
            identifier = slugify(item.get("ticker") or item.get("company_name") or "")
            existing = merged_by_id.get(identifier)
            if not existing:
                merged_by_id[identifier] = item
                continue
            preferred = dict(existing)
            for key in ("company_name", "ticker", "rationale", "why_now", "why_not_now", "vertical_summary", "horizontal_summary", "diligence_note"):
                if not preferred.get(key) and item.get(key):
                    preferred[key] = item[key]
            preferred["screen_score"] = max(int(existing.get("screen_score") or 0), int(item.get("screen_score") or 0))
            preferred["source_count"] = max(int(existing.get("source_count") or 0), int(item.get("source_count") or 0))
            if normalize_confidence(str(item.get("confidence") or "medium")) == "high":
                preferred["confidence"] = "high"
            merged_by_id[identifier] = preferred
    combined = list(merged_by_id.values())
    combined.sort(key=screen_sort_key, reverse=True)
    return combined


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
        company_name = clean_company_name(company_name or ticker)
        market_hint = str(item.get("market") or market).strip() or market
        if not company_name and not ticker:
            continue
        if not is_market_compatible_candidate(market=market, ticker=ticker, company_name=company_name or ticker, market_hint=market_hint):
            continue
        identifier = slugify(ticker or company_name)
        if identifier in seen:
            continue
        seen.add(identifier)
        normalized.append(
            {
                "company_name": company_name or ticker,
                "ticker": ticker,
                "market": market.upper().strip() or market,
                "rationale": clean_research_summary(str(item.get("rationale") or item.get("why") or f"{company_name or ticker} 值得进一步研究。")),
                "screen_score": max(0, min(100, int(item.get("screen_score") or 50))),
                "confidence": normalize_confidence(str(item.get("confidence") or "medium")),
                "source_count": max(1, int(item.get("source_count") or 1)),
                "angle": str(item.get("angle") or theme).strip() or theme,
                "why_now": clean_research_summary(str(item.get("why_now") or item.get("rationale") or ""))
                or str(item.get("why_now") or "").strip(),
                "why_not_now": clean_research_summary(str(item.get("why_not_now") or "")),
                "exclusion_reason": clean_research_summary(str(item.get("exclusion_reason") or item.get("why_not_now") or "")),
                "vertical_summary": clean_research_summary(str(item.get("vertical_summary") or "")),
                "horizontal_summary": clean_research_summary(str(item.get("horizontal_summary") or "")),
                "diligence_note": clean_research_summary(str(item.get("diligence_note") or "")),
                "evidence_snapshot": item.get("evidence_snapshot") if isinstance(item.get("evidence_snapshot"), list) else [],
            }
        )
    normalized.sort(key=screen_sort_key, reverse=True)
    return normalized


def build_screening_fallback_candidates(evidence: list[dict[str, str]], *, theme: str, market: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence:
        title = f"{item.get('title', '')} {item.get('claim', '')}".strip()
        excerpt = str(item.get("excerpt") or "")
        identities: list[tuple[str, str]] = []
        if market.upper() == "US":
            identities = extract_identity_hints("\n".join([title, excerpt]))
        else:
            match = re.search(r"([A-Za-z\u4e00-\u9fff]+)[(（]?\s*(\d{6})(?:\.?(?:SH|SZ))?[)）]?", title)
            if match:
                company_name = match.group(1).strip("-_ ")
                raw_code = match.group(2)
                identities = [(company_name, normalize_ticker(raw_code, "SSE" if raw_code.startswith("6") else "SZSE", market))]
        for company_name, ticker in identities:
            if not is_market_compatible_candidate(market=market, ticker=ticker, company_name=company_name or ticker, market_hint=market):
                continue
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


def looks_like_stock_identifier(value: str, market: str) -> bool:
    text = value.strip()
    if not text or contains_cjk(text) or " " in text:
        return False
    normalized = normalize_ticker(text, "", market)
    if market.upper() == "CN":
        return bool(re.fullmatch(r"\d{6}(?:\.(?:SH|SZ))?", normalized))
    if market.upper() == "US":
        return looks_like_us_ticker(normalized)
    return bool(re.fullmatch(r"[A-Z0-9.\-]{1,12}", normalized.upper()))


def resolve_research_request(*, identifier: str, ticker: str | None, market: str, market_positional: str | None = None) -> dict[str, str | None]:
    resolved_market = (market or market_positional or "CN").strip().upper() or "CN"
    clean_identifier = identifier.strip()
    ticker_hint = (ticker or "").strip()
    if ticker_hint:
        resolved_ticker = normalize_ticker(ticker_hint, "", resolved_market)
        stock_name = clean_identifier or resolved_ticker
        return {"stock_name": stock_name, "ticker": resolved_ticker, "market": resolved_market}
    if looks_like_stock_identifier(clean_identifier, resolved_market):
        resolved_ticker = normalize_ticker(clean_identifier, "", resolved_market)
        return {"stock_name": resolved_ticker, "ticker": resolved_ticker, "market": resolved_market}
    return {"stock_name": clean_identifier, "ticker": None, "market": resolved_market}


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
