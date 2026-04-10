---
title: Improve stock-research-desk
goal: Make stock-research-desk a high-trust multi-agent stock research CLI with robust sector screening, clean entity normalization, and daily-usable outputs.
autonomy_mode: aggressive_in_scope
continuity: cross_thread_cross_day
publish_mode: checkpoint_commit
risk_budget: medium
github_repo: wd041216-bit/stock-research-desk
work_sources:
  - local_tests
  - ci_failures
  - runtime_failures
  - todo_fixme
  - docs_handoff_gaps
  - github_issues
  - github_pr_reviews
  - github_discussions
stop_reasons:
  - needs_user_decision
  - external_blocker
  - risk_budget_exceeded
  - no_safe_work
  - mission_complete
---

# Mission

## In Scope

- Repository code, tests, docs, CI, and backlog items directly related to the current project.
- Follow-up work discovered through repo signals or GitHub signals.

## Out Of Scope

- New product lines or marketing tracks not implied by the current repository.
- Large irreversible architecture shifts without evidence.

## Success Signals

- The current mission is moving through verified checkpoints.
- `next_action` always points at the next safe, high-leverage task.
