# Dockerfile
# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt requirements.txt

# Устанавливаем зависимости
# Обновляем pip и устанавливаем зависимости без кэша
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создаем пользователя без root-прав
RUN useradd --create-home appuser
WORKDIR /home/appuser/app # Устанавливаем рабочую директорию для пользователя
USER appuser # Переключаемся на пользователя

# Копируем код приложения в контейнер (уже в директорию пользователя)
# Убедимся, что права доступа позволяют пользователю читать файлы
COPY --chown=appuser:appuser . .

# Указываем Flask, где искать приложение
ENV FLASK_APP=app.py
# Указываем порт по умолчанию, если $PORT не установлен (Render его установит)
ENV PORT=8080
# УБРАН ENV FLASK_SECRET_KEY='default_secret_key_change_me'
# Приложение должно получать FLASK_SECRET_KEY из переменных окружения при запуске

# Открываем порт, который будет слушать Gunicorn (Render использует переменную $PORT)
# EXPOSE директива больше для документации, Gunicorn будет слушать порт из CMD
# EXPOSE ${PORT} # Можно оставить или убрать

# Команда для запуска приложения с использованием Gunicorn (shell form)
# Оболочка подставит значение переменной $PORT
# Запускаем от имени appuser
CMD gunicorn --bind 0.0.0.0:$PORT app:app
