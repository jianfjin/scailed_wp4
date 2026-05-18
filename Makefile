.PHONY: test verify-tasks smoke-test ci

test:
	python3 -m pytest tests -q
	python3 -m compileall pathfinder api scripts
	npm run build --prefix frontend
	openspec validate add-merged-pathfinder-v1 --strict

verify-tasks:
	python3 scripts/verify_tasks.py --strict

smoke-test:
	bash deploy/smoke-test.sh

ci: test verify-tasks smoke-test
