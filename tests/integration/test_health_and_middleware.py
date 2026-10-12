"""
HTTP-darajadagi endpoint va middleware integratsiya testlari.

MUHIM: boshqa barcha integratsiya testlari servislarni (masalan,
`PaymeService`) to'g'ridan-to'g'ri chaqiradi -- ASGI ilovaning o'ziga
hech qachon HTTP so'rov yuborilmaydi. Shu sababli `app/main.py` va undagi
middleware'lar (shu jumladan quyida test qilinayotgan `/health` va
`RequestIDMiddleware`) coverage hisobotida doim 0% bo'lib chiqqan --
ular hech qachon import/instantiate qilinmagan edi. Bu fayl aynan shu
bo'shliqni yopadi: haqiqiy ASGI ilova (`app.main.app`) `httpx.AsyncClient`
+ `ASGITransport` orqali ishga tushiriladi.

MUHIM -- nega `fastapi.testclient.TestClient` EMAS: birinchi urinishda
sinxron `TestClient` ishlatilgan edi, lekin u ichki AnyIO portal orqali
ALOHIDA event loop'da ishlaydi. Shu loyihada `redis_client` va DB engine
modul darajasidagi SINGLETON'lar (qarang: tests/conftest.py docstring'i
-- xuddi shu muammo u yerda ham tasviрlangan), ya'ni ular birinchi
ishlatilgan event loop'ga "yopishib qoladi". `TestClient` so'rovni o'z
alohida loop'ida yuborgani uchun, keyin pytest-asyncio'ning `db_session`/
`_reset_redis_connection_pool` fixture'lari BOSHQA (pytest-asyncio'ning
o'z) loop'ida tozalashga urinib, "Event loop is closed" xatosini
keltirib chiqargan (real Docker testida aniqlangan). `AsyncClient` +
`ASGITransport` esa so'rovni TO'G'RIDAN-TO'G'RI joriy test
coroutine'ining o'zida (demak xuddi shu pytest-asyncio event loop'ida)
bajaradi -- boshqa barcha testlar bilan bir xil loop, muammo yo'q.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_reports_ok_when_db_and_redis_are_reachable() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_health_check_response_carries_a_request_id_header() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_request_id_header_sent_by_client_is_echoed_back_unchanged() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": "test-fixed-id-123"})

    assert response.headers["X-Request-ID"] == "test-fixed-id-123"
