# Agent setup and verification

Open the checkout root in the client. Share the branch and task ID. Git supplies the current source and context, while each worktree has its own local media and graph cache.

| Client | Project setup |
| --- | --- |
| Codex | Open the checkout root so Codex discovers `AGENTS.md`. Run the shared commands using its terminal tool. |
| Google Antigravity | Open the same checkout as a workspace and select Gemini or Claude where enabled. Current versions discover workspace `AGENTS.md`. Use the terminal for the shared graph workflow. |
| Gemini CLI | On an installed build, add `AGENTS.md` to the existing `context.fileName` setting in `.gemini/settings.json`. Confirm with `/memory show`. |
| Claude Code | v2.1.277 or later can load `AGENTS.md` directly when its Project instructions setting and parent instructions permit it. If your session requires `CLAUDE.md`, add a root file containing only `@AGENTS.md`. |

References: [Antigravity discovery](https://antigravity.google/docs/customization-discovery?tab=cli), [Gemini CLI context](https://geminicli.com/docs/cli/gemini-md/), [Claude Code instructions](https://code.claude.com/docs/en/memory), [Graphify](https://github.com/Graphify-Labs/graphify).

## Shared commands

```sh
make status
make check-docs
make test-target TEST=test_engine.EngineTests.test_production_approval_gate
make test
make check-costs
```

`make check-costs` uses mocked suppliers to exercise per-job approval, budgets, cache reuse and failure reservations.

For local graph navigation, install the open-source CLI in an isolated environment.

```sh
python3 -m venv .venv-graphify
.venv-graphify/bin/python -m pip install graphifyy
make graph
make graph-query Q='audio_metrics'
```

Every client can use the same index in a given checkout. The wrapper stamps source inputs and the graph hash, rejects stale or missing results, and gives a source-search fallback. Rebuild after source changes or checkout switches. Source, tests, shared docs and configuration are the freshness inputs. Use the Markdown files directly for current project guidance. Graphify's local update command requires no model API. The repo uses no client-specific installers or hooks.

## Session pickup smoke test

Start a new Codex session with this prompt, then repeat it in Antigravity with the same checkout and task. Use it in Claude Code or Gemini CLI to check their setup.

> Resume the active task using this checkout. Report the branch, HEAD and dirty state. Identify the task, locate `qc.check` via the local graph or targeted search, and run the listed approval test. Record what you verified and hand back the next step. Leave production code untouched for this smoke test.

Use a single writer per branch. For simultaneous changes, use separate branches and worktrees. Review the diff and Git status before adding files or handing off. Commit agreed changes and share the branch and commit hash. For consequential changes, use a reviewed PR and require human approval before merging. Configure protected main and required review rules when a remote host is selected. Local production controls enforce paid authorization and creative approval independently of Git hosting.

## Verification on 2026-11-13

- In Codex, exercised repository-only pickup of AE-001 with `make status`, the handoff, module map, and a targeted symbol lookup. The source located `audio_metrics` and its caller `qc.check` in `atmosphere/qc.py`. The targeted approval test passed.
- Graphify 0.9.108 built and refreshed the local index on Apple Silicon. The shared query found `audio_metrics` at `atmosphere/qc.py:18`. Tests verified rejection of stale inputs and changed graph contents. Graphify's installer help lists Codex, Antigravity, Gemini CLI and Claude Code. The shared workflow uses the underlying Graphify CLI directly.
- `make check-docs` passed. `make test` passed 10 tests, and `make check-costs` passed both offline cost-control tests.
- The Codex CLI was present and logged in. The Antigravity IDE version command returned 1.107.0 on arm64. An independent fresh Codex session, authenticated Antigravity pickup and the full round-trip are still unverified. Standalone Gemini and Claude commands were unavailable on PATH.
