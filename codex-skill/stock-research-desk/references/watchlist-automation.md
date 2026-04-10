# Watchlist Automation

For recurring coverage, prefer Codex automations over the repo's legacy internal watchlist scheduler.

Recommended automation behavior:

- task: refresh one stock or one watchlist bucket
- cadence: user-defined
- search policy:
  - Codex web search/open first
  - `cross-validated-search` only on explicit web errors
- output:
  - Chinese DOCX report
  - English DOCX report
  - optional JSON payload if the user wants machine-readable output
- delivery path:
  - `~/Desktop/Stock Research Desk/reports/`
  - `~/Desktop/Stock Research Desk/digests/`

Suggested automation checklist:

1. load prior memo context from the desktop workspace if present
2. gather fresh evidence
3. run the same multi-agent council
4. update target prices with horizons
5. write two DOCX files
6. open an inbox item with the refreshed verdict and file paths
