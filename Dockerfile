# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Метаданные
LABEL maintainer="Ivanomsk"
LABEL description="Санитар Дурдома - Telegram бот для управления VPN и прокси"
LABEL version="2.0.0"

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаём необходимые директории
RUN mkdir -p bot_data/logs bot_data/vpn_configs bot_data/backups

# Устанавливаем права
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Открываем порт для веб-интерфейса
EXPOSE 5050

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5050/login')" || exit 1

# Запуск бота и веб-интерфейса
CMD ["sh", "-c", "python main.py & python web/app.py"]
