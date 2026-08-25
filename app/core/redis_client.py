"""
Async Redis ulanishi — OTP kodlarni, refresh token'larni va rate-limit
hisoblagichlarini saqlash uchun ishlatiladi.
"""

from redis import asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
)


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency sifatida ishlatish uchun."""
    return redis_client
