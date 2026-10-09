# infra — стенд «Проверка пакета документов на субсидию»

Собирает репозитории организации [sber-vibe](https://github.com/sber-vibe) в один Docker Compose стенд за nginx.

```text
           :80 (HTTP_PORT)
браузер ──► nginx ──┬── /api/*, /health ──► backend   (sber-vibe/Backend, Spring Boot, :8080)
                    └── всё остальное   ──► frontend  (sber-vibe/Frontend, Next.js, :3000)
```

Наружу публикуется только nginx. Backend и frontend доступны лишь внутри сети compose.

## Запуск

Нужны Git и Docker Desktop (или Docker Engine с Compose v2).

```sh
git clone --recursive https://github.com/sber-vibe/infra.git
cd infra
cp .env.example .env        # при необходимости поменять HTTP_PORT
docker compose up -d --build
```

Откройте http://localhost (или `http://localhost:<HTTP_PORT>`). Проверка готовности:

```sh
docker compose ps           # все сервисы должны быть healthy
curl http://localhost/health  # {"status":"UP",...}
```

Если репозиторий склонирован без `--recursive`: `git submodule update --init`.

Остановить: `docker compose down`.

## Маршруты nginx

| Путь | Куда | Примечание |
|---|---|---|
| `/` | frontend | рабочее место специалиста |
| `/api/` | backend | тело запроса до 11 МБ (файл до 10 МБ + multipart); при превышении — `413` в формате Problem Details |
| `/health` | backend `/actuator/health` | доступность без чувствительных данных |
| `/nginx-health` | nginx | healthcheck самого прокси |
| `/_next/static/` | frontend | кэш на год, имена файлов с хешами |

Адреса сервисов nginx резолвит через Docker DNS при каждом запросе, поэтому
`docker compose up -d --build backend` не требует перезапуска nginx.

## Версии сервисов

`backend/` и `frontend/` — git submodules, закреплённые на конкретных коммитах `main`.
Обновить до последних `main`:

```sh
git submodule update --remote
git add backend frontend
git commit -m "chore: обновить backend и frontend"
docker compose up -d --build
```

## Переменные (`.env`)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `HTTP_PORT` | `80` | Порт стенда на хосте |
| `NEXT_PUBLIC_AUTO_CLASSIFY` | `false` | `true`, когда backend сам определяет тип документа по содержимому |
| `NEXT_PUBLIC_CONFIDENCE_THRESHOLD` | `0.8` | Порог пометки «требует подтверждения специалиста» |
| `NEXT_PUBLIC_OIDC_ISSUER`, `NEXT_PUBLIC_OIDC_CLIENT_ID` | пусто | Keycloak; пусто — демо-вход |

Переменные `NEXT_PUBLIC_*` встраиваются во frontend при сборке: после изменения выполните `docker compose build frontend`.
Секреты в Git не добавляются, `.env` в `.gitignore`.

## Проверено

- `docker compose up -d --build` с нуля: backend, frontend и nginx в статусе healthy.
- Через nginx: `/health`, страницы, `/api/v1/*`; загрузка 9 МБ — `201`, 10,5 МиБ — `413` от backend, 12 МиБ — `413` от nginx (JSON).
- E2E-сценарий специалиста из `frontend/e2e` (Playwright, десктоп и телефон) против стенда:
  `cd frontend && E2E_BASE_URL=http://localhost npm run e2e`.

## Чего пока нет

По [плану команды](https://github.com/sber-vibe/subsidy-checker/blob/main/IMPLEMENTATION_PLAN.md) в стенд ещё войдут PostgreSQL с volume (данные должны переживать перезапуск), Keycloak и локальная модель (Ollama).
Текущий backend хранит данные в памяти и не использует БД. Добавлять неиспользуемые сервисы заранее не стали, их подключат вместе с поддержкой в backend.
