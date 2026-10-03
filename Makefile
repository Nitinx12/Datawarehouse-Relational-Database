PY = .venv/Scripts/python.exe

.PHONY: help pipeline no-extract extract source-tests staging staging-tests
.PHONY: warehouse warehouse-tests analytics analytics-tests master test gx gx-build lint format

help:
	@echo "pipeline         full extract-to-master run (main.py)"
	@echo "no-extract       full run without Spark extracts"
	@echo "extract source-tests staging staging-tests warehouse warehouse-tests analytics analytics-tests master"
	@echo "                 run one pipeline stage"
	@echo "test             unit + smoke + dq + gx suites"
	@echo "gx               run all GX layer and master gates"
	@echo "gx-build         rebuild GX project from specs"
	@echo "lint format      ruff check / format"

pipeline:
	$(PY) main.py

no-extract:
	$(PY) main.py --skip extract

extract:
	$(PY) main.py --only extract

source-tests:
	$(PY) main.py --only source-tests

staging:
	$(PY) main.py --only staging

staging-tests:
	$(PY) main.py --only staging-tests

warehouse:
	$(PY) main.py --only warehouse

warehouse-tests:
	$(PY) main.py --only warehouse-tests

analytics:
	$(PY) main.py --only analytics

analytics-tests:
	$(PY) main.py --only analytics-tests

master:
	$(PY) main.py --only master

test:
	$(PY) scripts/run_all_tests.py

gx:
	$(PY) scripts/run_gx_validations.py

gx-build:
	$(PY) scripts/setup_gx_project.py

lint:
	$(PY) -m ruff check main.py scripts tests

format:
	$(PY) -m ruff format main.py scripts tests
