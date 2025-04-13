# Dockerfile
# Используем официальный образ Python
FROM python:3.9

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt requirements.txt

# Устанавливаем зависимости
# Обновляем pip и устанавливаем зависимости без кэша
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- ИЗМЕНЕНИЕ: Используем adduser и добавляем проверку ---
# Создаем пользователя без пароля и лишних вопросов, затем проверяем его существование
RUN adduser --disabled-password --gecos "" appuser && id appuser

# Устанавливаем рабочую директорию для пользователя (можно оставить /app, если права позволяют)
# WORKDIR /home/appuser/app # Можно закомментировать или оставить /app
# Переключаемся на пользователя
USER appuser

# Копируем код приложения в контейнер
# Права должны быть ОК, так как копируем ПОСЛЕ создания пользователя
# Но WORKDIR теперь /app, поэтому копируем в /app
COPY --chown=appuser:appuser . /app

# Указываем Flask, где искать приложение
ENV FLASK_APP=app.py
# Указываем порт по умолчанию, если $PORT не установлен (Render его установит)
ENV PORT=8080

# Команда для запуска приложения с использованием Gunicorn (shell form)
# Оболочка подставит значение переменной $PORT
# Запускаем от имени appuser
CMD gunicorn --bind 0.0.0.0:$PORT app:app
