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

## Работа с репозиторием

- main — рабочая версия
- новая задача — новая ветка, потом pull request
- пароли и токены в .env, не коммитим
