# Watchlist Automation

For recurring coverage, prefer Codex automations over the repo's legacy internal watchlist scheduler.

Recommended automation behavior:

- task: refresh one stock or one watchlist bucket
- cadence: user-defined
- search policy:
  - Codex web search/open first
  - `cross-validated-search` only on explicit web errors
- output:
  - one desktop DOCX report with Chinese and English in separate sections
  - hidden JSON payload only if machine-readable follow-up state is needed
- delivery path:
  - `~/Desktop/<timestamp>-<ticker-or-name>.docx`
  - internal state under `~/.stock-research-desk/`

Suggested automation checklist:

1. load prior memo context from the internal memory workspace if present
2. gather fresh evidence
3. run the same multi-agent council
4. update target prices with horizons
5. write one final DOCX file to the desktop
6. open an inbox item with the refreshed verdict and file paths
