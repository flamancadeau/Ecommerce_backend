.PHONY: help install migrate run test clean db-shell celery-worker celery-beat seed load-test freeze

help:
	@echo "Available commands:"
	@echo "  install     Install dependencies"
	@echo "  migrate     Run database migrations"
	@echo "  run         Run development server"
	@echo "  test        Run tests with pytest"
	@echo "  clean       Clean pycache files"
	@echo "  db-shell    Open database shell"
	@echo "  celery-worker  Start Celery worker"
	@echo "  celery-beat    Start Celery beat scheduler"
	@echo "  seed        Seed database with test data"
	@echo "  load-test   Run load tests"
	@echo "  freeze      Update requirements.txt from installed packages"

install:
	pip install -r requirements.txt

freeze:
	pip freeze > requirements.txt

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

run:
	python manage.py runserver

test:
	pytest

test-verbose:
	pytest -v

test-coverage:
	pytest --cov=apps --cov-report=html

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".eggs" -exec rm -rf {} +

db-shell:
	python manage.py dbshell

celery-worker:
	celery -A ecommerce worker --loglevel=info

celery-beat:
	celery -A ecommerce beat --loglevel=info

seed:
	python manage.py seed_data

load-test:
	python scripts/load_test.py

requirements-dev:
	pip install pytest pytest-django pytest-cov black flake8 isort
	pip freeze | grep -E "pytest|black|flake8|isort" > requirements-dev.txt
