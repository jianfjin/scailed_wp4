# SCAILED Pathfinder V1 — Makefile
# Primary gate: make gate (runs smoke test + verify tasks + unit tests)

.PHONY: test smoke gate verify clean

test:
	python3 -m pytest tests/ -v

smoke:
	bash deploy/smoke-test.sh

verify:
	python3 scripts/verify_tasks.py --strict

gate: smoke verify test
	@echo "✅ All gates passed — ready for merge."
