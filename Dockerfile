# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt requirements.txt

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения в контейнер
COPY . .

# Указываем Flask, где искать приложение
ENV FLASK_APP=app.py
# Устанавливаем переменную окружения для секретного ключа (лучше переопределить при запуске)
ENV FLASK_SECRET_KEY='default_secret_key_change_me'
# Указываем порт по умолчанию, если $PORT не установлен (хотя Render его установит)
ENV PORT=8080

# Открываем порт, который будет слушать Gunicorn (Render использует переменную $PORT)
# EXPOSE директива больше для документации, Gunicorn будет слушать порт из CMD
# EXPOSE ${PORT} # Можно оставить или убрать

# Команда для запуска приложения с использованием Gunicorn (shell form)
# Оболочка подставит значение переменной $PORT
CMD gunicorn --bind 0.0.0.0:$PORT app:app
