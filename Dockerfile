# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt requirements.txt

# Устанавливаем зависимости
# --no-cache-dir чтобы не хранить кэш pip и уменьшить размер образа
# --upgrade pip чтобы убедиться, что используется последняя версия pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения в контейнер
COPY . .

# Указываем Flask, где искать приложение
ENV FLASK_APP=app.py
# Устанавливаем переменную окружения для секретного ключа (лучше переопределить при запуске)
ENV FLASK_SECRET_KEY='default_secret_key_change_me'
# Указываем порт, который будет слушать Gunicorn (Render ожидает $PORT или 10000)
ENV PORT=8080

# Открываем порт, на котором будет работать Gunicorn
EXPOSE ${PORT}

# Команда для запуска приложения с использованием Gunicorn
# bind 0.0.0.0 чтобы приложение было доступно извне контейнера
# workers = 3 - хорошее начало, можно настроить
# Используем переменную окружения PORT
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "app:app"]

# Альтернативная команда для запуска с Flask development server (для отладки)
# CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
