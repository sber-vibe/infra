# Backend: что нужно для задач фронтенда FE-01…FE-06

Правила взаимодействия, по которым уже работает frontend (`main` в `sber-vibe/Frontend`, коммит `7ec92f1`).
Полный контракт: `Frontend/docs/API_CONTRACT.md`. Реквизиты заявки отдельно описаны в `BACKEND_REQUISITES.md`.

## Что сломается на стенде без доработки backend

| Возможность frontend | Что нужно от backend | Без этого |
|---|---|---|
| Создание заявки | `GET /programs` и `POST /applications` с одной программой | заявку создать нельзя |
| Загрузка без типа | `type` в загрузке необязателен | загрузка без выбранного типа падает с `400` |
| Исправление типа | `PATCH` документа | «Сервер пока не поддерживает исправление типа» |
| Просмотр DOC/DOCX/XLS/XLSX | `GET …/preview` | только скачивание оригинала |
| Статусы файлов | `processingStatus` и `outcome` у документа | все файлы «Нет результата обработки», зелёного итога нет |

## FE-01. Итог только по явному ответу сервера

Frontend больше ничего не додумывает. Зелёный статус появляется только там, где его прямо прислал сервер.

**Документ** (`DocumentView`):

| Поле | Правило |
|---|---|
| `processingStatus` | обязателен всегда: `UPLOADED`, `CLASSIFYING`, `EXTRACTING`, `CHECKING`, `DONE`, `FAILED`. Без поля frontend пишет «Нет результата обработки» |
| `outcome` | итог по файлу после проверки: `PASSED`, `ATTENTION`, `ERRORS`. Только `PASSED` даёт зелёную отметку. Отсутствие замечаний успехом не считается |
| `processingError` | при `FAILED` — понятная причина по-русски |
| `type` / `detectedType` | `UNKNOWN` или `null` — тип не определён, это никогда не успех |

**Отчёт** (`report.status`): `PASSED`, `ATTENTION`, `ERRORS`, `PROCESSING`.

- Сервер не отдаёт `PASSED`, если в пакете есть файлы не в `DONE`, файлы с `FAILED` или с неопределённым типом.
  Если отдаст, frontend всё равно покажет «Результат неполный».
- Неизвестный frontend-у статус показывается нейтрально, как есть.
- Каждая проблема — отдельное замечание в `findings` с `severity`, `documentId`, `field`, `rule`, `message`.

## FE-02. Загрузка без типа и обязательный перечень программ

**`GET /programs`** — обязателен. Без него или без активных программ frontend не даёт создать заявку.

```json
[ { "code": "INNOVATION", "name": "Инновационный проект", "active": true,
    "documents": [ { "type": "APPLICATION", "requirement": "REQUIRED" },
                   { "type": "CONFORMITY_CERTIFICATE", "requirement": "CONDITIONAL",
                     "condition": "если продукция подлежит сертификации" } ] } ]
```

**`POST /applications`** — тело `{ "programCode": "INNOVATION" }` или `{ "programCode": null }`
(автоопределение предлагается, только когда перечень программ получен).

**`POST /applications/{id}/documents`** — multipart, поле `file`; поле `type` **необязательное**.

- Без `type` тип определяет сервер по содержимому, а не по имени файла.
- Сразу ответ `201` с `processingStatus: "UPLOADED"`, обработка в фоне.
- Если `type` передан, это тип от специалиста: `typeSource: "SPECIALIST"`.

## FE-03. Исправление типа одним запросом

**`PATCH /applications/{id}/documents/{documentId}`** → документ

```json
{ "type": "GUARANTEE_LETTER" }
```

- `id` документа и оригинал файла не меняются.
- В ответе: `type` — новый, `typeSource: "SPECIALIST"`, `typeChangedBy` — имя из токена, `typeChangedAt` — время сервера.
- `detectedType` (вывод модели) не перезаписывается: frontend показывает «модель предлагала …».
- После правки отчёт сбрасывается (`report: null`) и пересчитывается комплектность; в журнал — `DOCUMENT_TYPE_CHANGED`.
- Ошибка — Problem Details с понятным `detail`. Frontend при ошибке файл не перезагружает и не удаляет.

## FE-04. Связка «программа → комплектность → замечания → решение → журнал»

Frontend показывает только то, что пришло с сервера.

- `report.completeness[]` — комплектность по перечню программы:
  `{ type, status: FOUND | MISSING | CONDITIONAL_MISSING | EXTRA, requirement, documentIds, condition, canUpload }`.
  Отсутствующий обязательный — ошибка; применимый условный — замечание; неприменимый условный не выводится.
- `POST /applications/{id}/decision` `{ decision: ACCEPTED | RETURNED | REJECTED, comment }` → заявка с
  `decision: { decision, comment, decidedBy, decidedAt }`. Решение хранится отдельно от автоотчёта и видно после обновления страницы.
- `GET /applications/{id}/journal` — события обработки, проверки, правок и решений.
- Администратор: `GET/POST/PUT /admin/programs`, `GET/PUT /admin/rules`. Изменённое правило сразу применяется
  при следующей проверке.

## FE-05. Просмотр DOC/DOCX/XLS/XLSX

**`GET /applications/{id}/documents/{documentId}/preview`**

| Ответ | Когда |
|---|---|
| `200` `application/pdf` или `text/html` | версия для просмотра готова |
| `202` + заголовок `Retry-After: <секунды>` | версия ещё готовится; frontend повторит запрос (до 20 раз) |
| Problem Details `422` (или другой код) с `detail` | конвертация не удалась — `detail` покажется специалисту |

- HTML-версия показывается без скриптов, поэтому должна быть самодостаточной (стили внутри, без внешних ресурсов).
- Оригинал по-прежнему отдаётся `GET /applications/{id}/documents/{documentId}`.
- Доступ к preview проверяется так же, как к оригиналу.

## FE-06. Ошибки модели, повтор, связь и сессия

- **Ошибка модели:** документ получает `processingStatus: "FAILED"` и `processingError` («Модель не ответила за 60 секунд»).
  Остальные файлы продолжают обрабатываться.
- **Повтор:** `POST /applications/{id}/documents/{documentId}/reprocess` → документ в `UPLOADED`/`PENDING`,
  дальше обычная обработка до `DONE` или `FAILED`. Повтор пишется в журнал.
- **Опрос:** frontend опрашивает `GET /applications/{id}` каждые 2 с, пока есть файлы не в `DONE`/`FAILED`
  или `report.status = "PROCESSING"`. При сетевых ошибках повторяет реже и после 5 неудач останавливается.
  Значит, обработка не должна застревать в промежуточном статусе навсегда: зависшее задание переводится в `FAILED`.
- **Сессия:** на запрос без токена или с истёкшим токеном — `401`. Frontend на любой `401` отправляет на вход
  и считает операцию невыполненной. Нет прав — `403` (опрос при этом прекращается).
- Ответ на изменяющий запрос не должен быть «успешным», если изменение не сохранено.

## Как проверить

- Документ без обработки отдаётся с `processingStatus`, а не без поля.
- Пакет с одним `FAILED` не получает `report.status: "PASSED"`.
- Загрузка без `type` → `201`, тип определён сервером.
- `PATCH` типа сохраняет `id`, заполняет `typeChangedBy`/`typeChangedAt`, `detectedType` прежний.
- `GET …/preview` для DOCX: сначала `202`, затем `200` с PDF или HTML.
- Запрос с истёкшим токеном → `401`.
