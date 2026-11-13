PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
GRAPHIFY ?= $(if $(wildcard .venv-graphify/bin/graphify),.venv-graphify/bin/graphify,graphify)
TEST ?= test_engine

.PHONY: status check-docs test test-target check-costs graph graph-query

status:
	$(PYTHON) scripts/workspace.py status

check-docs:
	$(PYTHON) scripts/workspace.py check

test:
	$(PYTHON) -m unittest discover -s tests -v

test-target:
	PYTHONPATH=tests $(PYTHON) -m unittest -v "$(TEST)"

check-costs:
	PYTHONPATH=tests $(PYTHON) -m unittest -v test_engine.EngineTests.test_paid_request_gate_and_cache test_engine.EngineTests.test_failed_paid_request_stays_reserved

graph:
	GRAPHIFY_BIN="$(GRAPHIFY)" $(PYTHON) scripts/workspace.py graph

graph-query:
	@GRAPHIFY_BIN="$(GRAPHIFY)" $(PYTHON) scripts/workspace.py query

export Q
