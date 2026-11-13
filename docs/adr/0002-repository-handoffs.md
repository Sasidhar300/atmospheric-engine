# ADR 0002 · Repository handoffs

Adopted for the shared workflow.

Keep one shared instruction file and a Markdown task per handoff. Require a live Git snapshot before an agent relies on a task's branch or working-tree notes. Keep Graphify optional and refreshable through the same shell command in each client. The local index may lag source or be missing on a new checkout. Verify results in code and use targeted search when the index is unavailable.
