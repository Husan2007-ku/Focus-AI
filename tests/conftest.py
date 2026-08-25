"""
Umumiy pytest fixture'lari.

MUHIM DIZAYN QARORI — ALOHIDA TEST ENGINE: ilovaning umumiy `engine`'i
(connection pool bilan) ishlatilmaydi, chunki pytest-asyncio har bir test
uchun YANGI event loop yaratadi, pool esa eski loop'ga "yopishib qolgan"
ulanishlarni qayta ishlatishga urinib, `MissingGreenlet` / "attached to a
different loop" xatolarini keltirib chiqaradi. Shuning uchun testlar uchun
`NullPool` bilan alohida engine ishlatiladi — har bir ulanish yangi
yaratiladi va darhol yopiladi, hech qanday holat keyingi testga o'tmaydi.

XUDDI SHU MUAMMO REDIS UCHUN HAM MAVJUD: ilovaning umumiy `redis_client`
obyekti (`app.core.redis_client`) — modul darajasida yaratilgan yagona
ulanish puli. Birinchi test uni qaysi event loop'da ishlatsa, pul o'sha
loop'ga "bog'lanib qoladi". Keyingi test (yangi event loop bilan) shu
pulni ishlatishga uringanda "Event loop is closed" xatosi chiqadi — bu
xato NAVBAT bilan (har ikkinchi testda) yuzaga kelishi shu diagnozni
tasdiqlaydi. Yechim: har test tugagach ulanish pulini majburan uzish —
keyingi test yangi ulanish ochadi (joriy event loop'ga bog'langan holda).

TRANZAKSIYA ISOLATSIYASI: har bir test o'z ichki tranzaksiyasida (savepoint)
ishlaydi. Servislar ichida `await self.db.commit()` chaqirilsa ham, bu
faqat savepoint'ni "bo'shatadi" — tashqi tranzaksiya test oxirida ROLLBACK
qilinadi. Natijada testlar bir-biriga ta'sir qilmaydi va haqiqiy dev
bazasiga hech qanday doimiy o'zgarish yozilmaydi.

MUHIM — `expire_on_commit=False`: standart holatda SQLAlchemy `commit()`dan
keyin barcha obyekt maydonlarini "eskirgan" deb belgilaydi va keyingi
murojaatda ularni qayta bazadan o'qiydi. Bu qayta o'qish sinxron atribut
o'qish (`user.id`) ichida sodir bo'lganda, async muhitda `MissingGreenlet`
xatosini keltirib chiqaradi. `expire_on_commit=False` bu muammoni oldini
oladi — xuddi ilovaning o'zidagi asosiy sessiya sozlamasi bilan bir xil
(`app/core/database.py`).
"""

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.user import AuthProvider, User

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    connection = await test_engine.connect()
    outer_transaction = await connection.begin()

    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    yield session

    await session.close()
    await outer_transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture(autouse=True)
async def _reset_redis_connection_pool() -> AsyncGenerator[None, None]:
    yield
    await redis_client.connection_pool.disconnect()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        phone_number=f"+99890{uuid.uuid4().int % 10_000_000:07d}",
        primary_auth_provider=AuthProvider.PHONE,
        full_name="Test Foydalanuvchi",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
