# Checkpoint: Clean title-style company names into legal/trading entity names more reliably.

- Time: 2026-04-10T08:36:35+00:00
- Item ID: plan-decomposition-b5186b6d44
- Verification: passed
- Stop reason: none

## Summary

Hardened title-style company-name normalization by preferring cleaner trading-entity names during identity recovery and candidate merging, fixing suffix-only parses for US equities while preserving stage-one dossier fields.

## Verification

76 tests passed, and direct runtime probes showed noisy labels like "Nexalin Technology Stock Price Today NXL" now normalize to "Nexalin Technology" with ticker NXL during both identity recovery and merged finalist generation.
