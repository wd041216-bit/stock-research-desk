# Contributing

Contributions are welcome, especially around:

- evidence-quality ranking
- more reliable ticker and company normalization
- stronger target-price extraction
- clearer memo quality and testing

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## Scope

Please keep the repo focused on:

- cloud-only single-name stock research
- evidence-aware memo generation
- multi-agent debate and scenario workflows

Please do not turn it into:

- an auto-trading bot
- a portfolio manager
- a generic crawler platform

## Pull Requests

- keep changes narrow
- include tests when behavior changes
- prefer clearer outputs over more complicated orchestration
