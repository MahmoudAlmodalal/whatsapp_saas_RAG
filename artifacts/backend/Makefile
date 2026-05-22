##############################################################################
# Makefile — WhatsApp AI SaaS Test & Dev Commands
##############################################################################
.PHONY: help test test-unit test-integration test-security test-performance \
        test-e2e coverage lint typecheck clean install dev

PYTHON     := python
PYTEST     := pytest
DOCKER_COMPOSE := docker-compose

# ─── Default ─────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  WhatsApp AI SaaS — Developer Commands"
	@echo "  ────────────────────────────────────────"
	@echo "  make install          Install all dependencies (app + test)"
	@echo "  make dev              Start the full stack with docker-compose"
	@echo ""
	@echo "  make test             Run ALL tests (unit + integration + security)"
	@echo "  make test-unit        Run unit tests only (no Docker needed)"
	@echo "  make test-integration Run integration tests (requires docker-compose up)"
	@echo "  make test-security    Run security & injection tests"
	@echo "  make test-performance Run Locust load tests (requires docker-compose up)"
	@echo "  make test-e2e         Run Playwright end-to-end tests"
	@echo ""
	@echo "  make coverage         Generate HTML + XML coverage report"
	@echo "  make lint             Run ruff linter"
	@echo "  make typecheck        Run mypy type checker"
	@echo "  make clean            Remove generated files (__pycache__, .pytest_cache, etc.)"
	@echo ""

# ─── Install ──────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

# ─── Dev Stack ────────────────────────────────────────────────────────────────
dev:
	$(DOCKER_COMPOSE) up --build

# ─── Testing ──────────────────────────────────────────────────────────────────
test:
	$(PYTEST) tests/ -ra --tb=short

test-unit:
	$(PYTEST) tests/unit/ -m "unit" -ra --tb=short -v

test-integration:
	$(PYTEST) tests/integration/ -m "integration" -ra --tb=short -v

test-security:
	$(PYTEST) tests/security/ tests/unit/test_security.py -m "security or unit" -ra --tb=short -v

test-performance:
	locust -f tests/performance/locustfile.py --headless \
	  --users 100 --spawn-rate 10 --run-time 60s \
	  --host http://localhost:8000

test-e2e:
	$(PYTEST) tests/e2e/ -m "e2e" --tb=short -v

# ─── Coverage ─────────────────────────────────────────────────────────────────
coverage:
	$(PYTEST) tests/unit/ tests/integration/ tests/security/ \
	  --cov=app --cov=tasks \
	  --cov-report=html:htmlcov \
	  --cov-report=xml:coverage.xml \
	  --cov-report=term-missing \
	  --cov-fail-under=85
	@echo "\n✅ Coverage report generated: htmlcov/index.html"

# ─── Code Quality ─────────────────────────────────────────────────────────────
lint:
	ruff check app/ tasks/ tests/ --fix
	ruff format app/ tasks/ tests/ --check

typecheck:
	mypy app/ tasks/ --ignore-missing-imports

# ─── Cleanup ──────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "coverage.xml" -delete
	find . -name ".coverage" -delete
	@echo "✅ Cleaned up generated files."
