.PHONY: help install migrate migrate-celery-beat makemigrations run test test-verbose test-coverage clean db-shell celery-worker celery-beat celery-flower seed load-test freeze requirements-dev

help:
	@echo "Available commands:"
	@echo "  install           Install dependencies"
	@echo "  migrate           Run database migrations"
	@echo "  migrate-celery-beat  Run django_celery_beat migrations"
	@echo "  makemigrations    Create new migrations"
	@echo "  run               Run development server"
	@echo "  test              Run tests with pytest"
	@echo "  test-verbose      Run tests with verbose output"
	@echo "  test-coverage     Run tests with coverage report"
	@echo "  clean             Clean pycache files and build artifacts"
	@echo "  db-shell          Open database shell"
	@echo "  celery-worker     Start Celery worker"
	@echo "  celery-beat       Start Celery beat scheduler"
	@echo "  celery-flower     Start Flower monitoring dashboard"
	@echo "  seed              Seed database with test data"
	@echo "  load-test         Run load tests"
	@echo "  freeze            Update requirements.txt from installed packages"
	@echo "  requirements-dev  Install and create development requirements"

install:
	pip install -r requirements.txt

freeze:
	pip freeze > requirements.txt

migrate:
	python manage.py migrate

migrate-celery-beat:
	python manage.py migrate django_celery_beat

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
	celery -A ecommerce worker -l info

celery-beat:
	celery -A ecommerce beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

celery-flower:
	celery -A ecommerce flower

seed:
	python manage.py seed_data

load-test:
	python scripts/load_test.py

requirements-dev:
	pip install pytest pytest-django pytest-cov black flake8 isort
	pip freeze | grep -E "pytest|black|flake8|isort" > requirements-dev.txt