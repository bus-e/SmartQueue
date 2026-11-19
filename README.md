# SmartQueue

Электронная очередь: приложение, сайт и телеграм-бот.

## Запуск

```
cp .env.example .env
docker compose up --build
```

Сервер: http://localhost:8080/api/v1/health
API: http://localhost:8080/docs

## Тесты

```
cd server
pip install -r requirements-dev.txt
pytest
```
