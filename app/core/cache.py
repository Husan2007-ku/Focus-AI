"""
Umumiy Redis-keshlash yordamchisi — tez-tez o'qiladigan, lekin kamdan-kam
o'zgaradigan ma'lumotlar uchun (masalan, gamification summary).

Nega decorator emas, oddiy funksiyalar: Python decoratorlari async metodlar
va `self` argumentini to'g'ri boshqarish uchun qo'shimcha murakkablik
qo'shadi. Ikki kichik funksiya (`get_cached`/`set_cached`) chaqiruvchi
kodda ochiq-oydin va debug qilish osonroq bo'ladi.
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)

CACHE_KEY_PREFIX = "cache"


def _build_key(namespace: str, identifier: str) -> str:
    return f"{CACHE_KEY_PREFIX}:{namespace}:{identifier}"


async def get_cached(namespace: str, identifier: str) -> Any | None:
    key = _build_key(namespace, identifier)
    try:
        raw = await redis_client.get(key)
    except Exception as exc:
        # Kesh Redis'dan o'qilmasa ham, ilova ishlashda davom etishi kerak —
        # kesh muvaffaqiyatsizligi hech qachon so'rovni to'xtatmasligi kerak.
        logger.warning("cache_read_failed", namespace=namespace, error=str(exc))
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def set_cached(namespace: str, identifier: str, value: Any, ttl_seconds: int) -> None:
    key = _build_key(namespace, identifier)
    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as exc:
        logger.warning("cache_write_failed", namespace=namespace, error=str(exc))


async def invalidate_cached(namespace: str, identifier: str) -> None:
    key = _build_key(namespace, identifier)
    try:
        await redis_client.delete(key)
    except Exception as exc:
        logger.warning("cache_invalidate_failed", namespace=namespace, error=str(exc))
