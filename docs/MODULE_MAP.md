# Module map

Use this index to select the smallest relevant source and test surface.

| Concern | Start here | Follow into |
| --- | --- | --- |
| CLI and previews | `atmosphere/cli.py`, `recipe`, `make_media` | Config, project store, render and QC |
| Scene validation | `atmosphere/config.py`, `load` | `scenes/rainy_apartment.yaml` |
| Drawing and motion | `atmosphere/visuals.py`, `Compositor.render` | Window masks, approved layers and phase |
| Music and environmental stems | `atmosphere/audio.py`, `compose`, `environment`, `mix` | CLI recipe and WAV exports |
| Video and seams | `atmosphere/render.py`, `stream`, `seam_preview` | `atmosphere/qc.py`, `check` |
| Assets and approvals | `atmosphere/project.py`, `Project.approved`, `review` | CLI recipe, asset ledger |
| Spending and APIs | `atmosphere/project.py`, `Project.request`, `reconcile` | `atmosphere/providers.py`, budget in YAML |
| Regression tests | `tests/test_engine.py` | `make test-target TEST=test_engine.EngineTests.test_production_approval_gate` |
| Handoff and graph | `scripts/workspace.py`, `Makefile` | `docs/HANDOFF.md`, `tasks/`, `tests/test_workspace.py` |
