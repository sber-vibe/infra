"""
Приёмочный прогон backend на синтетическом пакете (testdata/package) по требованиям кейса.

Проверяет не «что умеет текущая заготовка», а то, что требует ТЗ: классификация по содержимому,
извлечение полей, правила и арифметика на сервере, сверка ИНН, сохранение после перезапуска,
закрытость оригиналов, пограничные файлы. FAIL — это задача для backend.

Только стандартная библиотека Python. Запуск при поднятом стенде infra:
    python testdata/acceptance.py --base http://localhost --restart "docker compose restart backend"
Результат: таблица в консоли и testdata/acceptance-result.json.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent
PKG = ROOT / "package"
EDGE = PKG / "edge-cases"

# тип, который специалист выбрал бы вручную в текущем контракте (у заготовки только 4 типа)
MANUAL_TYPE = {
    "APPLICATION": "APPLICATION",
    "REGISTRATION_EXTRACT": "REGISTRATION_EXTRACT",
    "COST_ESTIMATE": "COST_ESTIMATE",
}


@dataclass
class Result:
    id: str
    requirement: str
    title: str
    status: str  # PASS | FAIL | INFO
    expected: str
    actual: str
    evidence: dict = field(default_factory=dict)


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return r.status, dict(r.headers), raw
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def json(self, method: str, path: str, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        status, headers, raw = self.call(method, path, body, {"Content-Type": "application/json"} if body else {})
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = raw[:200].decode("utf-8", "replace")
        return status, data, headers

    def upload(self, app_id: str, file: Path, doc_type: str | None):
        boundary = uuid.uuid4().hex
        parts = []
        if doc_type:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n{doc_type}\r\n'.encode())
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n".encode() + file.read_bytes() + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        status, headers, raw = self.call(
            "POST", f"/api/v1/applications/{app_id}/documents", b"".join(parts),
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = raw[:200].decode("utf-8", "replace")
        return status, data


def short(data, limit=220) -> str:
    text = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    return text if len(text) <= limit else text[:limit] + "…"


def run(base: str, restart_cmd: str | None) -> list[Result]:
    api = Api(base)
    expected = json.loads((PKG / "expected.json").read_text(encoding="utf-8"))
    docs = expected["documents"]
    results: list[Result] = []
    add = lambda *a, **kw: results.append(Result(*a, **kw))  # noqa: E731

    status, health, _ = api.json("GET", "/health")
    add("A01", "Д1", "Стенд отвечает /health", "PASS" if status == 200 and health.get("status") == "UP" else "FAIL",
        "200 {status: UP}", f"{status} {short(health)}")

    status, types, _ = api.json("GET", "/api/v1/document-types")
    add("A02", "Д10", "Реестр типов документов содержит 8 видов", "PASS" if isinstance(types, list) and len(types) >= 8 else "FAIL",
        "≥ 8 конфигурируемых типов (заявление, выписка, смета, справка ФНС, согласие, …)",
        f"{status} {short(types)} — {len(types) if isinstance(types, list) else 0} типа(ов)")

    org = {"applicantName": expected["organization"], "inn": expected["inn"], "projectName": "Цифровая платформа учёта",
           "requestedAmount": expected["requested_amount"]}
    status, app, _ = api.json("POST", "/api/v1/applications", org)
    app_id = app["id"] if status == 201 else None
    add("A03", "Д3", "Создание проверки", "PASS" if app_id else "FAIL", "201 + id", f"{status} {short(app)}")
    if not app_id:
        return results

    # --- Д9: тип по содержимому — загрузка без поля type
    first = next(iter(docs))
    status, data = api.upload(app_id, PKG / first, None)
    add("A04", "Д9", "Загрузка без указания типа (тип определяет сервер по содержимому)",
        "PASS" if status == 201 and isinstance(data, dict) and (data.get("detectedType") or data.get("type")) == docs[first]["type"] else "FAIL",
        f"201, detectedType={docs[first]['type']}", f"{status} {short(data)}")

    # загрузка пакета так, как позволяет текущий контракт (тип выбирает специалист)
    uploaded = {}
    for name, meta in docs.items():
        manual = MANUAL_TYPE.get(meta["type"], "SUPPORTING_DOCUMENT")
        status, data = api.upload(app_id, PKG / name, manual)
        uploaded[name] = (status, data, manual)
    ok = all(s == 201 for s, _, _ in uploaded.values())
    add("A05", "Д3", "Загрузка пакета из 7 файлов (PDF, PDF-скан, JPG, PNG, DOCX) с ручным типом",
        "PASS" if ok else "FAIL", "201 для каждого файла",
        "; ".join(f"{n}: {s}" for n, (s, _, _) in uploaded.items()))
    collapsed = [n for n, (_, _, t) in uploaded.items() if t == "SUPPORTING_DOCUMENT"]
    add("A06", "Д10", "Каждый из видов документов можно указать/распознать", "FAIL" if collapsed else "PASS",
        "Справка ФНС, бизнес-план, реквизиты, доверенность — отдельные типы",
        f"нет подходящего типа, загружены как SUPPORTING_DOCUMENT: {', '.join(collapsed)}")

    status, app, _ = api.json("GET", f"/api/v1/applications/{app_id}")
    sample = app["documents"][0] if status == 200 and app["documents"] else {}
    has_ai = any(k in sample for k in ("detectedType", "confidence", "fields"))
    add("A07", "Д5", "Документ содержит результат модели: тип, confidence, извлечённые поля", "PASS" if has_ai else "FAIL",
        "detectedType, confidence, fields[] (например inn, requested_amount)", f"поля документа: {sorted(sample.keys())}")

    # --- Д11: правила, арифметика, cross-check
    status, report, _ = api.json("POST", f"/api/v1/applications/{app_id}/check")
    codes = {f.get("code") for f in (report or {}).get("findings", [])} if isinstance(report, dict) else set()
    for rid, req, title, code in [
        ("A08", "Д11", "Комплектность: нет согласия на обработку ПДн", "MISSING_DOCUMENT"),
        ("A09", "Д11", "Арифметика: сумма заявления 850 000 > сметы 800 000", "AMOUNT_GT_COST"),
        ("A10", "BONUS", "Сверка ИНН между заявлением и выпиской ЕГРЮЛ", "INN_MISMATCH"),
        ("A11", "BONUS", "Срок действия справки ФНС истекает через 12 дней", "DOCUMENT_EXPIRES_SOON"),
    ]:
        planted = next(p for p in expected["planted_findings"] if p["code"] == code)
        found = code in codes and (code != "MISSING_DOCUMENT" or any(
            f.get("code") == code and f.get("documentType") == "CONSENT" for f in report.get("findings", [])))
        add(rid, req, title, "PASS" if found else "FAIL", f"замечание {code}: {planted['message']}",
            f"коды в отчёте: {sorted(c for c in codes if c)}")
    add("A12", "Д11", "Итоговый статус пакета с заложенными ошибками", "FAIL" if report and report.get("status") == "REVIEW_REQUIRED" else "PASS",
        "пакет требует доработки (есть критические ошибки)", f"status={report.get('status') if isinstance(report, dict) else report}",
        {"report": report})

    # --- Д4: перезапуск
    if restart_cmd:
        subprocess.run(restart_cmd, shell=True, check=False, capture_output=True)
        for _ in range(60):
            s, h, _ = api.json("GET", "/health")
            if s == 200 and isinstance(h, dict) and h.get("status") == "UP":
                break
            time.sleep(2)
        status, data, _ = api.json("GET", f"/api/v1/applications/{app_id}")
        add("A13", "Д4", "Проверка и документы сохраняются после перезапуска backend", "PASS" if status == 200 else "FAIL",
            "200, те же документы и отчёт", f"{status} {short(data)}")
        if status != 200:
            status, app, _ = api.json("POST", "/api/v1/applications", org)
            app_id = app["id"]
            for name, (_, _, manual) in uploaded.items():
                api.upload(app_id, PKG / name, manual)
    else:
        add("A13", "Д4", "Сохранение после перезапуска", "INFO", "200 после рестарта", "не проверялось (--restart не задан)")

    # --- исправление типа специалистом
    status, app, _ = api.json("GET", f"/api/v1/applications/{app_id}")
    doc = app["documents"][0]
    status, data, _ = api.json("PATCH", f"/api/v1/applications/{app_id}/documents/{doc['id']}", {"type": "REGISTRATION_EXTRACT"})
    add("A14", "SCORE", "Специалист исправляет тип/поля документа (PATCH)", "PASS" if status == 200 else "FAIL",
        "200 + пересчёт результата", f"{status} {short(data)}")

    # --- оригинал: имя, тип, доступ
    status, headers, raw = api.call("GET", f"/api/v1/applications/{app_id}/documents/{doc['id']}")
    disp = headers.get("Content-Disposition", headers.get("content-disposition", ""))
    ctype = headers.get("Content-Type", headers.get("content-type", ""))
    add("A15", "Д3", "Оригинал отдаётся с исходным именем и типом", "PASS" if doc["filename"] in disp and "octet-stream" not in ctype else "FAIL",
        f'Content-Type по содержимому, filename="{doc["filename"]}"', f"Content-Type: {ctype}; {disp}")
    add("A16", "SCORE", "Оригинал закрыт: без авторизации доступ запрещён", "PASS" if status in (401, 403) else "FAIL",
        "401/403 без токена", f"{status}, {len(raw)} байт без авторизации")

    # --- пограничные файлы
    edge_app = api.json("POST", "/api/v1/applications", {**org, "applicantName": "ООО «Пограничные случаи»"})[1]["id"]
    expect_edge = {
        "Смета расходов (копия).PDF": (201, "Д3"), "empty.pdf": (400, "Д3"), "big.pdf": (413, "Д3"),
        "virus.exe": (415, "Д3"), "fake.pdf": (415, "Д3"),
    }
    big = EDGE / "big.pdf"
    if not big.exists():  # 10,5 МиБ в git не храним — создаём на лету
        big.write_bytes((PKG / "1.pdf").read_bytes() + b"%" + b"0" * int(10.5 * 1024 * 1024))
    for i, (name, (want, req)) in enumerate(expect_edge.items(), start=17):
        status, data = api.upload(edge_app, EDGE / name, "COST_ESTIMATE")
        extra = ""
        if status == 201 and isinstance(data, dict) and data.get("filename") != name:
            extra = f" — имя искажено: {data.get('filename')!r}"
        add(f"A{i}", req, f"Пограничный файл {name}: {expected['edge_cases'][name]}",
            "PASS" if status == want and not extra else "FAIL", str(want), f"{status} {short(data)}{extra}")

    status, data = api.upload(edge_app, EDGE / "zayavlenie.pdf", None)
    add("A22", "Д9", "Имя «zayavlenie.pdf», внутри смета — тип по содержимому",
        "PASS" if status == 201 and isinstance(data, dict) and data.get("detectedType") == "COST_ESTIMATE" else "FAIL",
        "detectedType=COST_ESTIMATE", f"{status} {short(data)}")

    # --- устойчивость демо-стенда: общий лимит хранилища
    filler_app = api.json("POST", "/api/v1/applications", {**org, "applicantName": "ООО «Заполнение хранилища»"})[1]["id"]
    nine = EDGE / "_nine.pdf"
    nine.write_bytes(b"%PDF-1.4\n%" + b"0" * (9 * 1024 * 1024))
    statuses = []
    for _ in range(8):  # заполняем общий лимит хранилища одной проверкой
        st, last = api.upload(filler_app, nine, "SUPPORTING_DOCUMENT")
        statuses.append(st)
        if st != 201:
            break
    status, data = api.upload(app_id, nine, "SUPPORTING_DOCUMENT")
    nine.unlink()
    add("A23", "Д1", "Загрузки одной проверки не блокируют остальные проверки",
        "PASS" if status == 201 else "FAIL", "201 для файла 9 МБ в другой проверке",
        f"в одну проверку 9 МБ: {statuses} ({short(last, 80)}); затем 9 МБ в другую проверку: {status} {short(data, 120)}")
    status, app, _ = api.json("GET", f"/api/v1/applications/{filler_app}")
    for d in app.get("documents", []):
        api.call("DELETE", f"/api/v1/applications/{filler_app}/documents/{d['id']}")

    # --- валидация заявки
    for rid, title, payload, want in [
        ("A24", "ИНН с неверной контрольной цифрой", {**org, "inn": "1234567890"}, 400),
        ("A25", "Сумма с долями копейки", {**org, "requestedAmount": 850000.555}, 400),
    ]:
        status, data, _ = api.json("POST", "/api/v1/applications", payload)
        add(rid, "SCORE", title, "PASS" if status == want else "FAIL", str(want), f"{status} {short(data, 120)}")
    status, data, _ = api.json("POST", "/api/v1/applications", {**org, "inn": "12"})
    detail = json.dumps(data, ensure_ascii=False) if data else ""
    add("A26", "SCORE", "Ошибка валидации указывает поле", "PASS" if "inn" in detail else "FAIL",
        "Problem Details с указанием поля inn", f"{status} {short(data)}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost")
    parser.add_argument("--restart", help="команда перезапуска backend, например: docker compose restart backend")
    parser.add_argument("--out", default=str(ROOT / "acceptance-result.json"))
    args = parser.parse_args()
    results = run(args.base, args.restart)
    width = max(len(r.title) for r in results)
    for r in results:
        print(f"{r.id}  {r.status:<4}  {r.requirement:<5}  {r.title:<{width}}  | {r.actual}")
    passed = sum(r.status == "PASS" for r in results)
    failed = sum(r.status == "FAIL" for r in results)
    print(f"\nPASS {passed}  FAIL {failed}  всего {len(results)}")
    Path(args.out).write_text(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
