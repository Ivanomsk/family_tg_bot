# Makefile для проекта Санитар Дурдома

.PHONY: help install test test-cov run docker-build docker-up docker-down docker-logs clean

help:
	@echo "Доступные команды:"
	@echo "  make install        - Установка зависимостей"
	@echo "  make test           - Запуск тестов"
	@echo "  make test-cov       - Запуск тестов с покрытием"
	@echo "  make run            - Запуск бота локально"
	@echo "  make docker-build   - Сборка Docker образа"
	@echo "  make docker-up      - Запуск Docker контейнера"
	@echo "  make docker-down    - Остановка Docker контейнера"
	@echo "  make docker-logs    - Просмотр логов контейнера"
	@echo "  make clean          - Очистка временных файлов"

install:
	pip install -r requirements.txt

test:
	pytest -v

test-cov:
	pytest --cov=. --cov-report=html -v
	@echo "Отчет о покрытии: htmlcov/index.html"

run:
	python main.py

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage 2>/dev/null || true
