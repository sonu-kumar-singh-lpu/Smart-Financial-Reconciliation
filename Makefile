.PHONY: help install test lint format docker-build docker-run clean

help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run Docker container"
	@echo "  clean       - Clean up generated files"

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

lint:
	flake8 src/
	black --check src/
	isort --check-only src/

format:
	black src/
	isort src/

docker-build:
	docker build -t financial-reconciliation:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage