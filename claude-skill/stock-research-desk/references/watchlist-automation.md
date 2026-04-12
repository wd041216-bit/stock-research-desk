# Watchlist Automation Reference

This document describes how to set up and manage watchlist automations using Claude Code.

## Watchlist State

The watchlist is stored in `~/.stock-research-desk/watchlist.json` with this structure:

```json
[
  {
    "identifier": "赛腾股份",
    "ticker": "603283.SH",
    "market": "CN",
    "angle": "",
    "interval_hours": 168,
    "next_run": "2025-01-20T00:00:00Z",
    "last_report_path": "/Users/user/Desktop/20250113-603283.docx"
  }
]
```

## Adding a Watchlist Entry

```bash
./bin/research-stock watchlist add 赛腾股份 --market 中国 --interval 7d
```

Or via Claude Code:
1. Read `~/.stock-research-desk/watchlist.json`
2. Append a new entry
3. Write back

## Running Due Entries

```bash
./bin/research-stock watchlist run-due
```

Or via Claude Code:
1. Read `~/.stock-research-desk/watchlist.json`
2. Find entries where `next_run <= now`
3. For each due entry, run the full single-name research workflow
4. Generate bilingual DOCX memo to `~/Desktop/`
5. Update `next_run` to `now + interval_hours`
6. Update `last_report_path`
7. Write back `watchlist.json`

## Scheduling with Claude Code

For recurring watchlist refreshes, use Claude Code's scheduling capabilities:

1. Use `/schedule` or `CronCreate` to set up a recurring task
2. The task should check the watchlist and run due entries
3. Example schedule: check every 24 hours for due entries

## Email Integration

The Python CLI supports email-driven commands:
- `research: 赛腾股份 | | 中国`
- `screen: 中国机器人 | 3 | 中国`
- `watchlist add: 赛腾股份 | | 7d | 中国`
- `watchlist list`
- `watchlist run-due`

For Claude Code skill usage, prefer direct CLI commands or the watchlist JSON manipulation approach rather than email.