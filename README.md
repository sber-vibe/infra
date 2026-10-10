# infra — стенд «Проверка пакета документов на субсидию»

Собирает репозитории организации [sber-vibe](https://github.com/sber-vibe) в один Docker Compose стенд за nginx.

```text
           :80 (HTTP_PORT)
браузер ──► nginx ──┬── /api/*, /health ──► backend   (sber-vibe/Backend, Spring Boot, :8080)
                    ├── /kc/*            ──► keycloak  (Keycloak 26, :8080) ──► keycloak-db (PostgreSQL)
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
| `/api/` | backend | тело запроса до 51 MiB (файл до 50 MiB + multipart); при превышении — `413` в формате Problem Details |
| `/health` | backend `/actuator/health` | доступность без чувствительных данных |
| `/kc/` | keycloak | вход специалистов (OIDC), консоль администратора `/kc/admin` |
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
| `SUBSIDY_PUBLIC_URL` | `http://localhost` | Адрес стенда в браузере; от него строятся issuer и redirect URI Keycloak |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | `admin`, — | Администратор Keycloak (создаётся при первом запуске) |
| `KEYCLOAK_DB_PASSWORD` | — | Пароль PostgreSQL для Keycloak |
| `KEYCLOAK_DEMO_PASSWORD` | — | Пароль демо-пользователя `specialist` (роль `specialist`) |
| `KEYCLOAK_JWK_SET_URI` | внутренний адрес Keycloak | JWKS для проверки токенов backend; пусто — API закрыт с 503 |

Переменные `NEXT_PUBLIC_*` встраиваются во frontend при сборке: после изменения выполните `docker compose build frontend`.
Секреты в Git не добавляются, `.env` в `.gitignore`.

## Keycloak

Realm `subsidy` импортируется из [`keycloak/realm-subsidy.json`](keycloak/realm-subsidy.json) при первом запуске:
public client `subsidy-frontend` (Authorization Code + PKCE S256), роли `specialist` и `admin`, пользователь `specialist`.
Данные Keycloak лежат в volume `keycloak-db`, поэтому повторный импорт существующий realm не перезаписывает.
Чтобы применить изменения realm-файла или `SUBSIDY_PUBLIC_URL`, правьте realm в консоли или пересоздайте данные:
Предпочтительно менять существующий realm через консоль: удаление volumes уничтожает пользователей Keycloak и данные backend.

Issuer: `${SUBSIDY_PUBLIC_URL}/kc/realms/subsidy` — он же `NEXT_PUBLIC_OIDC_ISSUER`. Путь `/kc`, а не `/auth`: на `/auth/callback` frontend принимает код.
При смене порта или домена поменяйте `SUBSIDY_PUBLIC_URL` и `NEXT_PUBLIC_OIDC_ISSUER` вместе.
Backend проверяет `Authorization: Bearer …` на `/api/**`: подпись по JWKS (`http://keycloak:8080/kc/...` внутри сети), issuer `${SUBSIDY_PUBLIC_URL}/kc/realms/subsidy`, audience `subsidy-backend`, роль `specialist` или `admin`.
Пустой `KEYCLOAK_JWK_SET_URI=` в `.env` закрывает API с 503. Открытый локальный режим требует явного профиля backend `dev`.

## Проверено

- `docker compose up -d --build` с нуля: backend, frontend и nginx в статусе healthy.
- Через nginx: `/health`, страницы, `/api/v1/*`; загрузка 9 МБ — `201`, 10,5 МиБ — `413` от backend, 12 МиБ — `413` от nginx (JSON).
- E2E-сценарий специалиста из `frontend/e2e` (Playwright, десктоп и телефон) против стенда:
  `cd frontend && E2E_BASE_URL=http://localhost npm run e2e`.

## Тестовый пакет и приёмка backend

`testdata/package/` — синтетический пакет из 7 документов (PDF, PDF-скан, JPG, PNG, DOCX) с заложенными ошибками и пограничные файлы;
правильные ответы — в `expected.json`. `testdata/acceptance.py` проверяет backend по требованиям кейса:

```sh
python testdata/acceptance.py --base http://localhost --restart "docker compose restart backend"
```

Результаты и список задач для backend: [docs/BACKEND_TEST_REPORT.md](docs/BACKEND_TEST_REPORT.md).

## Хранение и доступ

Backend хранит заявки, оригиналы, отчёты, решения, настройки и аудит в H2 на volume `backend-data` (`/app/data`). Перезапуск и пересборка сохраняют данные; `docker compose down -v` удаляет их. Для резервной копии остановите backend и сохраните каталог volume. Один экземпляр backend работает с этой БД.
Ollama подключается через `OLLAMA_URL`; модель устанавливается отдельно на хосте. `AI_API_KEY` хранится только в локальном `.env`.

Realm-роли разделены: `admin` управляет настройками и журналом, `specialist` работает с заявками. Очередь общая для специалистов. Пользователь без этих ролей не получает доступ к рабочим данным.
Саморегистрация создаёт пользователя без рабочих ролей: после проверки заявки на доступ оператор назначает нужную роль в Keycloak. Демо-пользователь `specialist` имеет явную роль `specialist`.

Для существующего realm импорт не обновляет роли. В консоли Keycloak выберите realm `subsidy`, Realm roles → `default-roles-subsidy` → Associated roles и удалите `specialist`. Не удаляйте явную роль у уже одобренных специалистов. Уже выданные токены сохраняют прежние роли до истечения срока; для немедленного применения завершите пользовательские сессии.

Для администратора приложения используйте отдельного пользователя realm `subsidy` с единственной рабочей ролью `admin`, отдельным временным паролем и требованием UPDATE_PASSWORD. Учётная запись администратора master realm предназначена для консоли Keycloak. Автоматическое создание пользователя `subsidy-admin` в этот импорт не включено.

Основные проверки новой реализации: backend `AdminPersistenceTest`, `JwtSecurityTest`, `UnconfiguredSecurityTest` и HTTP-проверка CRUD программ. Старые результаты E2E выше относятся к предыдущей сборке.