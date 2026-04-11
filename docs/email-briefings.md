# Email Briefing Modes

`stock-research-desk` supports mailbox-driven workflows over standard IMAP + SMTP.

The point is not just remote triggering. The replies are formatted like a small research desk, so the inbox becomes a compact operating surface.

## Single-Name Desk Note

Triggered by:

- `research: 赛腾股份 |  | 中国`

Format:

- verdict
- confidence
- quick take
- top bull points
- key risks
- short / medium / long target prices
- attached memo path

## Screening Brief

Triggered by:

- `screen: 中国机器人 | 3 | 中国`

Format:

- initial candidate count
- second-screen pool count
- final recommendation count
- ranked names
- `why now`
- quick take
- target snapshot
- attached screening summary

## Morning Watchlist Brief

Triggered by:

- `watchlist run-due`

on most weekdays.

Format:

- refreshed name count
- highest-priority refresh
- target snapshot
- quick take per updated name
- refreshed memo attachments only for names that were actually due

## Weekly Watchlist Wrap

Also triggered by:

- `watchlist run-due`

but the desk promotes the email body into a weekly wrap on the start of the week.

Format:

- coverage count
- lead verdict
- target snapshot
- roll-up of refreshed names
- refreshed memo attachments only; the watchlist queue itself remains internal
