# Backend: реквизиты заявки берутся из документов

Правила взаимодействия frontend и backend для сценария создания заявки. Frontend уже работает по ним
(`main` в `sber-vibe/Frontend`). Полный контракт описан в `Frontend/docs/API_CONTRACT.md`.

## Сценарий кейса

1. Специалист авторизуется и нажимает «Новая заявка».
2. Выбирает программу субсидии или оставляет автоматическое определение.
3. Загружает пакет без предварительного заполнения ИНН, организации и сумм.
4. Система распознаёт документы и заполняет карточку заявки.
5. Специалист видит извлечённые значения рядом с оригиналами и разбирает замечания.

## Что срочно

Frontend при создании присылает только программу. Пока backend требует организацию, ИНН и сумму,
создание заявки падает с `400`. Правила 1 и 2 нужны в первую очередь, остальные включают извлечение и историю правок.

## 1. Создание заявки

`POST /api/v1/applications`

```json
{ "programCode": "INNOVATION" }
```

- `programCode` может быть `null` или отсутствовать: тогда программу определяет сервер из заявления.
- Других полей нет. Организацию, ИНН, проект и сумму специалист не вводит.
- Ответ `201` с заявкой, у которой реквизиты пока пустые.

## 2. Заявка: реквизиты из документов

`GET /api/v1/applications/{id}` и элементы `GET /api/v1/applications`:

- `applicantName`, `inn`, `projectName`, `requestedAmount` равны `null`, пока значение не извлечено
  или если его не удалось распознать.
- `programCode`, `programName` — программа субсидии; `programDetected: true`, если её определил сервер.
- `requisites` — реквизиты карточки с источником:

```json
"requisites": [
  { "name": "company_name", "value": "ООО «Ромашка»", "status": "RECOGNIZED",
    "documentId": "d1", "source": "Заявитель: ООО «Ромашка»", "confidence": 0.93 },
  { "name": "inn", "value": null, "status": "NOT_RECOGNIZED", "documentId": "d1" },
  { "name": "requested_amount", "value": 900000, "status": "RECOGNIZED", "documentId": "d1",
    "manuallyCorrected": true, "originalValue": 850000,
    "correctedBy": "Анна Петрова", "correctedAt": "2026-10-10T09:00:00Z" }
]
```

| Поле | Правило |
|---|---|
| `name` | `company_name`, `inn`, `kpp`, `project_name`, `requested_amount`; можно добавлять другие |
| `value` | строка или число; `null` — не распознано |
| `status` | `RECOGNIZED` или `NOT_RECOGNIZED` |
| `documentId` | документ, из которого взято значение: frontend открывает его рядом с карточкой |
| `source` | фрагмент текста документа, где найдено значение |
| `confidence` | уверенность 0..1 |
| `manuallyCorrected`, `originalValue`, `correctedBy`, `correctedAt` | история ручной правки, см. правило 5 |

- Значения верхнего уровня (`applicantName`, `inn`, …) совпадают с `value` соответствующих реквизитов.
- Реквизиты берутся из заявления (`APPLICATION`). Если заявлений несколько, из первого загруженного.
- Реквизиты пересчитываются после обработки, удаления или правки документа.

## 3. Загрузка документов и фоновая обработка

`POST /api/v1/applications/{id}/documents` (multipart: `file`, `type` необязателен)

- Сразу ответ `201` с `processingStatus: "UPLOADED"`. Распознавание идёт в фоне.
- Frontend каждые 2 секунды перечитывает `GET /applications/{id}`, пока есть документы не в `DONE`/`FAILED`.
- `processingStatus`: `UPLOADED` → `CLASSIFYING` / `EXTRACTING` → `DONE` или `FAILED`.
- При `FAILED` — `processingError`: понятная специалисту причина по-русски («Модель не ответила за 60 секунд»).
- Если модель занята, документ ждёт в очереди, а не падает с ошибкой.

Документ в ответе:

| Поле | Правило |
|---|---|
| `type` | тип, подтверждённый специалистом или сервером |
| `detectedType`, `confidence` | тип, определённый моделью, и уверенность; не определён — `null` |
| `typeSource` | `MODEL` или `SPECIALIST` |
| `typeChangedBy`, `typeChangedAt` | кто и когда исправил тип |
| `fields[]` | извлечённые поля: `{ name, value, status, confidence, source, manuallyCorrected, originalValue, correctedBy, correctedAt }` |

Имена полей документа: `company_name`, `inn`, `kpp`, `project_name`, `requested_amount`, `date` и другие
из `API_CONTRACT.md`. Суммы — числом, даты — `YYYY-MM-DD`.

## 4. Нераспознанные значения

- Не удалось прочитать значение → `value: null`, `status: "NOT_RECOGNIZED"`. Frontend показывает
  «Не распознано / требуется проверка».
- Нераспознанное значение не подставляется и не считается извлечённым. Угадывать или подставлять
  значения по умолчанию нельзя.
- Значение прочитано, но модель не уверена → значение есть, `status: "RECOGNIZED"`, низкий `confidence`,
  плюс замечание `WARNING` в отчёте.

## 5. Ручная правка с историей

`PATCH /api/v1/applications/{id}/documents/{documentId}` → документ

```json
{ "fields": [{ "name": "inn", "value": "6161234567" }] }
{ "type": "GUARANTEE_LETTER" }
```

Правка поля:
- `originalValue` — значение модели до первой правки. Повторные правки его не меняют. Если поле было
  не распознано, `originalValue: null`.
- `value` — новое значение, `status: "RECOGNIZED"`, `manuallyCorrected: true`.
- `correctedBy` — имя специалиста из токена (`preferred_username`), `correctedAt` — время правки.
- Соответствующий реквизит заявки обновляется так же.

Правка типа:
- `typeSource: "SPECIALIST"`, `typeChangedBy`, `typeChangedAt`.
- `detectedType` не меняется: frontend показывает «модель предлагала …».

После любой правки предыдущий отчёт сбрасывается (`report: null`), в журнал пишется `FIELD_CHANGED`
или `DOCUMENT_TYPE_CHANGED`.

`POST /api/v1/applications/{id}/documents/{documentId}/reprocess` → документ: повторная обработка после `FAILED`.

## 6. Проверка пакета

`POST /api/v1/applications/{id}/check`

- Арифметические проверки (суммы, доля собственных средств, совпадение сумм между документами) выполняются
  **только на числах из документов**.
- Если нужное число не распознано, проверка не считается пройденной: замечание `WARNING`
  «Не удалось проверить: сумма не распознана».
- Пока документы обрабатываются, `report.status: "PROCESSING"`.
- Замечания: `{ code, message, severity, documentType, documentId, field }`. `message` показывается специалисту
  как есть, по-русски.

## 7. Ошибки

Формат Problem Details (`application/problem+json`). Поле `detail` frontend показывает специалисту, поэтому
оно пишется понятно и по-русски.

## Как проверить

- `POST /applications` с `{}` и с `{ "programCode": null }` → `201`, реквизиты `null`.
- После обработки заявления заполнены `requisites` и значения верхнего уровня; нечитаемое поле → `NOT_RECOGNIZED`.
- Повторная правка поля не меняет `originalValue`; `correctedBy` — из токена.
- Проверка при нераспознанной сумме даёт `WARNING`, а не успех.
