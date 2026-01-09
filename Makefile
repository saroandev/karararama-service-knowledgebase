# RAG Project Makefile

.PHONY: help run run-dev run-prod streamlit streamlit-dev streamlit-prod run-all docker-up docker-down test clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# API Commands
run: ## Run API in development mode with auto-reload (ignores venv)
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8080 \
		--reload-exclude "venv/*" \
		--reload-exclude "*.pyc" \
		--reload-exclude "__pycache__" \
		--reload-exclude "test_output/*" \
		--reload-exclude ".git/*"

run-dev: run ## Alias for run

run-prod: ## Run API in production mode (no auto-reload)
	uvicorn api.main:app --host 0.0.0.0 --port 8080 --workers 4

run-simple: ## Run API with simple Python command
	python -m api.main

# Docker Commands
docker-up: ## Start all Docker services
	docker compose -p onedocs-service-knowledgebase up -d

docker-down: ## Stop all Docker services
	docker compose -p onedocs-service-knowledgebase down

docker-restart: ## Restart all Docker services
	docker compose -p onedocs-service-knowledgebase down && docker compose -p onedocs-service-knowledgebase up -d

docker-logs: ## Show Docker logs
	docker compose -p onedocs-service-knowledgebase logs -f

docker-ps: ## Show Docker services status
	docker compose -p onedocs-service-knowledgebase ps

# Database Commands
milvus-clean: ## Clean Milvus collection
	python scripts/cleanup_milvus.py

# Test Commands
test: ## Run all tests
	pytest

test-unit: ## Run unit tests only
	pytest -m unit

test-integration: ## Run integration tests
	pytest -m integration

# Cleanup Commands
clean: ## Clean cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf test_output
	rm -rf htmlcov
	rm -rf .coverage

clean-all: clean ## Clean everything including Docker volumes
	docker compose -p onedocs-service-knowledgebase down -v

# Installation Commands
install: ## Install dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt

# Git Commands
commit: ## Git add and commit with message
	@read -p "Commit message: " msg; \
	git add -A && git commit -m "$$msg"

push: ## Push to current branch
	git push origin $$(git branch --show-current)