# Source Quality Model

This repo does not trust raw web results equally.

## What It Rewards

- exchange filings
- regulator disclosures
- official investor relations pages
- higher-trust financial media
- evidence with cleaner claims and fewer portal artifacts

## What It Penalizes

- low-trust forum pages
- quote pages with almost no analytical content
- aggregation pages with navigation spam
- near-name collisions where the page is about another company

## Why This Matters

Without source quality control, a multi-agent research flow will often look sophisticated while still being driven by shallow or irrelevant pages.

The current pipeline uses:

- domain-level quality overrides
- blocked-source filtering
- candidate ranking
- duplicate suppression
- relevance checks against ticker and company signals

## Limitation

This is still public-web research.

It improves stability and credibility, but it does not replace:

- clean financial terminals
- management calls
- full filing models
- real buy-side diligence
