# Atmosphere Engine

## Start and hand off

1. Check the branch, HEAD and full working-tree status with `make status`. Read [the handoff](docs/HANDOFF.md), the linked task and the relevant section of [current state](docs/CURRENT_STATE.md). Compare recorded details with Git before relying on them.
2. Use [the module map](docs/MODULE_MAP.md), `make graph-query Q='symbol'` or targeted `rg` searches. Verify graph findings in source and tests. Follow callers, dependencies and downstream effects as needed.
3. Run focused checks, run the relevant broader tests and record exact commands and observed results. Update the task and handoff after meaningful changes. Use [the task template](tasks/TEMPLATE.md).

## Engineering and approvals

- Keep rendering headless, local-first and compatible with Apple Silicon. Preserve deterministic clocks, streamed frames, asset history and explicit creative approvals.
- Keep credentials in the environment and paid providers disabled by default. Tests must stay offline. Paid submissions require an authorized job and a budget reservation.
- Use one writer per branch. Use separate branches and worktrees for concurrent agents. Preserve other agents' edits and review the worktree before staging anything.
- Obtain explicit human approval for significant architecture changes, paid execution, new commercial dependencies, destructive operations, publication, replacement of approved assets, weakened security/licensing/cost controls, and consequential merges to protected main.
- Store handoff context in Git. Keep generated media, local asset binaries, credentials and graph caches out of commits. Record reproducible provenance.

See [shared workflows and client setup](docs/AGENT_SETUP.md).
