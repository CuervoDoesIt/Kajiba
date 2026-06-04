.PHONY: install dev test lint clean

install:
	pip install -e .

dev:
	pip install -e ".[all]"

test:
	pytest tests/ -v --cov=kajiba --cov-report=term-missing

lint:
	python -m py_compile src/kajiba/schema.py
	python -m py_compile src/kajiba/scrubber.py
	python -m py_compile src/kajiba/scorer.py
	python -m py_compile src/kajiba/collector.py
	python -m py_compile src/kajiba/cli.py

clean:
	rm -rf dist/ build/ *.egg-info/ src/*.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .coverage htmlcov/
