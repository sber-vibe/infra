# infra — стенд «Проверка пакета документов на субсидию»

Собирает репозитории организации [sber-vibe](https://github.com/sber-vibe) в один Docker Compose стенд за nginx.

```text
           :80 (HTTP_PORT)
браузер ──► nginx ──┬── /api/*, /health ──► backend   (sber-vibe/Backend, Spring Boot, :8080) ──► Ollama на ПК с моделью (OLLAMA_URL)
                    ├── /kc/*            ──► keycloak  (Keycloak 26, :8080) ──► keycloak-db (PostgreSQL)
                    └── всё остальное   ──► frontend  (sber-vibe/Frontend, Next.js, :3000)
```

Наружу публикуется только nginx. Backend и frontend доступны лишь внутри сети compose.
Модель Qwen3-VL работает в Ollama на отдельном ПК локальной сети. С ним общается только backend.

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

## AI-модуль (модель на отдельном ПК)

Backend анализирует документы мультимодальной моделью **Qwen3-VL** через **Ollama**. Ollama запущена на отдельном ПК
локальной сети, обычно с GPU, и в стенд не входит. Облачные AI API не используются: документы уходят только на этот ПК.
Обращения к модели идут только из AI-модуля backend.

```text
ПК стенда: backend ──HTTP :11434──► ПК с моделью: Ollama + qwen3-vl:4b-instruct
```

### Подготовка ПК с моделью (Windows)

1. Установить Ollama (https://ollama.com/download) и скачать модель, около 3 ГБ:
   ```powershell
   ollama pull qwen3-vl:4b-instruct
   ```
2. Разрешить подключения из сети: по умолчанию Ollama слушает только `127.0.0.1`. Модель держится в памяти 30 минут после запроса:
   ```powershell
   setx OLLAMA_HOST "0.0.0.0:11434"
   setx OLLAMA_KEEP_ALIVE "30m"
   ```
   Затем полностью закрыть Ollama (значок в трее → Quit) и запустить снова.
3. Открыть порт **только для ПК стенда** (PowerShell от администратора, вместо `192.168.1.20` подставить IP стенда):
   ```powershell
   New-NetFirewallRule -DisplayName "Ollama from subsidy stand" -Direction Inbound -Protocol TCP `
     -LocalPort 11434 -RemoteAddress 192.168.1.20 -Action Allow
   ```
4. Закрепить за ПК постоянный IP (резервирование DHCP на роутере), иначе адрес в `OLLAMA_URL` перестанет работать.
5. ПК не должен засыпать, пока идёт работа со стендом.

На Linux: `sudo systemctl edit ollama` → `Environment="OLLAMA_HOST=0.0.0.0:11434"`, затем `sudo systemctl restart ollama`
и правило файрвола для IP стенда.

### Настройка стенда

В `.env` указать адрес ПК с моделью и пересоздать backend:

```sh
# .env
OLLAMA_URL=http://192.168.1.50:11434
OLLAMA_MODEL=qwen3-vl:4b-instruct
```

```sh
docker compose up -d backend
# ПК с моделью доступен из контейнера backend и модель на месте
docker compose exec backend bash -c 'exec 3<>/dev/tcp/192.168.1.50/11434 && printf "GET /api/tags HTTP/1.0\r\n\r\n" >&3 && cat <&3' | grep qwen3-vl
```

Если Ollama запущена на том же компьютере, что и стенд: `OLLAMA_URL=http://host.docker.internal:11434`.

### Безопасность и ограничения

- У Ollama нет авторизации: любой, кто достаёт до порта 11434, может пользоваться моделью. Поэтому порт открывается только для IP стенда.
- Документы передаются по сети без шифрования. Подходит только доверенная локальная сеть; в другом случае нужен VPN
  (WireGuard или Tailscale) либо SSH-туннель, а `OLLAMA_URL` указывается на адрес туннеля.
- Если ПК с моделью выключен или недоступен, стенд работает. Обработка документа завершается понятной ошибкой «модель
  недоступна» с возможностью повторить, данные не выдумываются.
- Анализ идёт по одному документу за раз, через nginx запрос к `/api/` ждёт ответа до 120 с.

**Прямой AI API** `POST /api/v1/ai/analyze` (multipart, поле `file`, заголовок `X-Api-Key`) нужен для отладки и
интеграции. Без `AI_API_KEY` длиной от 32 символов он отвечает `503`. Фоновая обработка документов в заявках от ключа
не зависит. Ключ хранится только в `.env`. Снаружи стенда используйте HTTPS: ключ сам трафик не шифрует.

```sh
curl -X POST http://localhost/api/v1/ai/analyze -H "X-Api-Key: $AI_API_KEY" -F "file=@заявление.pdf"
```

Ответы при сбоях: `401` неверный ключ, `422` файл не обработан, `502` ошибка обработки, `503` модель недоступна
или занята, `504` тайм-аут. Ограничения и формат ответа описаны в README backend.

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
| `OLLAMA_URL` | — (обязательна) | Адрес Ollama на ПК с моделью, например `http://192.168.1.50:11434`; на этом же компьютере — `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | `qwen3-vl:4b-instruct` | Модель, скачанная на ПК с моделью |
| `AI_API_KEY` | пусто | Ключ прямого `POST /api/v1/ai/analyze` (от 32 символов); пусто — маршрут отвечает `503` |

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

Для подключения загрузок заявок к готовому AI API в локальной сети задайте в `.env` полный `AI_REMOTE_URL` (например `http://<адрес сервера>:8080/api/v1/ai/analyze`) и `AI_REMOTE_API_KEY`, затем выполните `docker compose up -d --build backend`. Backend отправляет оригинал документа как multipart с `X-Api-Key`; ключ не передаётся frontend и не сохраняется в Git. Если URL пуст, используется прямой Ollama. При недоступности сервера документ получает `FAILED` и допускает повторную обработку. Прямой локальный `/api/v1/ai/analyze` использует Ollama независимо от этого параметра.

Backend хранит заявки, оригиналы, отчёты, решения, настройки и аудит в H2 на volume `backend-data` (`/app/data`). Перезапуск и пересборка сохраняют данные; `docker compose down -v` удаляет их. Для резервной копии остановите backend и сохраните каталог volume. Один экземпляр backend работает с этой БД.
Ollama подключается через `OLLAMA_URL`; модель устанавливается отдельно на хосте. `AI_API_KEY` хранится только в локальном `.env`.

Realm-роли разделены: `admin` управляет настройками и журналом, `specialist` работает с заявками. Очередь общая для специалистов. Пользователь без этих ролей не получает доступ к рабочим данным.
Саморегистрация создаёт пользователя без рабочих ролей: после проверки заявки на доступ оператор назначает нужную роль в Keycloak. Демо-пользователь `specialist` имеет явную роль `specialist`.

Для существующего realm импорт не обновляет роли. В консоли Keycloak выберите realm `subsidy`, Realm roles → `default-roles-subsidy` → Associated roles и удалите `specialist`. Не удаляйте явную роль у уже одобренных специалистов. Уже выданные токены сохраняют прежние роли до истечения срока; для немедленного применения завершите пользовательские сессии.

Для администратора приложения используйте отдельного пользователя realm `subsidy` с единственной рабочей ролью `admin`, отдельным временным паролем и требованием UPDATE_PASSWORD. Учётная запись администратора master realm предназначена для консоли Keycloak. Автоматическое создание пользователя `subsidy-admin` в этот импорт не включено.

Основные проверки новой реализации: backend `AdminPersistenceTest`, `JwtSecurityTest`, `UnconfiguredSecurityTest` и HTTP-проверка CRUD программ. Старые результаты E2E выше относятся к предыдущей сборке.
