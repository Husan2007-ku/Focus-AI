"""
HTTP-darajadagi endpoint va middleware integratsiya testlari.

MUHIM: boshqa barcha integratsiya testlari servislarni (masalan,
`PaymeService`) to'g'ridan-to'g'ri chaqiradi -- ASGI ilovaning o'ziga
hech qachon HTTP so'rov yuborilmaydi. Shu sababli `app/main.py` va undagi
middleware'lar (shu jumladan quyida test qilinayotgan `/health` va
`RequestIDMiddleware`) coverage hisobotida doim 0% bo'lib chiqqan --
ular hech qachon import/instantiate qilinmagan edi. Bu fayl aynan shu
bo'shliqni yopadi: haqiqiy ASGI ilova (`app.main.app`) FastAPI
`TestClient` orqali ishga tushiriladi va chinakam HTTP so'rov yuboriladi.

`TestClient`ning o'zi `settings.DATABASE_URL` / `settings.REDIS_URL`ga
ulangan modul darajasidagi `AsyncSessionLocal` / `redis_client`dan
foydalanadi -- ya'ni boshqa integratsiya testlari ishlatayotgan AYNAN
shu test Postgres/Redis'iga ulanadi (faqat o'qish uchun: SELECT 1, PING).
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_check_reports_ok_when_db_and_redis_are_reachable() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


def test_health_check_response_carries_a_request_id_header() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_request_id_header_sent_by_client_is_echoed_back_unchanged() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-fixed-id-123"})

    assert response.headers["X-Request-ID"] == "test-fixed-id-123"
