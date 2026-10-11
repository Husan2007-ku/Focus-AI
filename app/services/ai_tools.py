"""
AI Agent uchun "tool"lar (funksiyalar) — Claude bu funksiyalarni chaqirish
orqali haqiqiy amallarni bajarishi mumkin.

XAVFSIZLIK QOIDASI: bu yerda faqat QAYTARILADIGAN va PAST XAVFLI amallar bor.
Pul bilan bog'liq amallar (moliyaviy maqsad yaratish, obuna sotib olish)
AI'ga berilmagan — ular har doim foydalanuvchining o'zi tomonidan, ilova
UI'sida aniq tasdiqlash orqali amalga oshirilishi kerak.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FocusAIException
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.focus import FocusSessionStartSchema
from app.services.focus_service import FocusSessionService
from app.services.gamification_service import GamificationService
from app.services.routine_service import RoutineService

logger = get_logger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "start_focus_session",
        "description": (
            "Foydalanuvchi uchun yangi fokus seansini boshlaydi. Foydalanuvchi "
            "aniq vaqt yoki bloklanadigan ilovalarni aytmagan bo'lsa, taxminiy "
            "qiymat ishlatishdan oldin undan so'ra."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "planned_duration_minutes": {
                    "type": "integer",
                    "description": "Fokus seansi davomiyligi daqiqalarda (1-480)",
                },
                "blocked_apps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Bloklanadigan ilovalar paket nomlari (ixtiyoriy)",
                },
            },
            "required": ["planned_duration_minutes"],
        },
    },
    {
        "name": "get_active_focus_session",
        "description": (
            "Foydalanuvchining hozir davom etayotgan fokus seansi haqida ma'lumot beradi "
            "(bo'lmasa, yo'qligini bildiradi)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_focus_history_summary",
        "description": (
            "Foydalanuvchining so'nggi fokus seanslari tarixi va umumiy statistikasini qaytaradi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Nechta oxirgi seansni ko'rish kerak (standart: 10)",
                }
            },
        },
    },
    {
        "name": "get_gamification_summary",
        "description": (
            "Foydalanuvchining joriy streak (ketma-ket kunlar), jami XP va qo'lga kiritgan "
            "yutuqlarini qaytaradi."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_today_routine",
        "description": (
            "Foydalanuvchining bugungi ertalabki rejasi va (agar kiritilgan bo'lsa) "
            "kechqurungi hisobotini qaytaradi."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


async def execute_tool(
    tool_name: str, tool_input: dict[str, Any], db: AsyncSession, user: User
) -> dict[str, Any]:
    """Tool nomiga qarab tegishli servis metodini chaqiradi.

    Natijani JSON-mos lug'at sifatida qaytaradi.
    """
    try:
        if tool_name == "start_focus_session":
            service = FocusSessionService(db)
            schema = FocusSessionStartSchema(
                planned_duration_minutes=tool_input["planned_duration_minutes"],
                blocked_apps=tool_input.get("blocked_apps"),
            )
            session = await service.start_session(user, schema)
            return {
                "success": True,
                "session_id": str(session.id),
                "status": session.status.value,
                "planned_duration_minutes": session.planned_duration_minutes,
            }

        if tool_name == "get_active_focus_session":
            service = FocusSessionService(db)
            session = await service.get_active_session(user)
            if session is None:
                return {"active_session": None}
            return {
                "active_session": {
                    "session_id": str(session.id),
                    "planned_duration_minutes": session.planned_duration_minutes,
                    "started_at": session.started_at.isoformat(),
                }
            }

        if tool_name == "get_focus_history_summary":
            service = FocusSessionService(db)
            limit = tool_input.get("limit", 10)
            items, total = await service.get_history(user, limit=limit)
            return {
                "total_sessions": total,
                "recent_sessions": [
                    {
                        "status": s.status.value,
                        "planned_minutes": s.planned_duration_minutes,
                        "actual_minutes": s.actual_duration_minutes,
                        "started_at": s.started_at.isoformat(),
                    }
                    for s in items
                ],
            }

        if tool_name == "get_gamification_summary":
            service = GamificationService(db)
            summary = await service.get_summary(user.id)
            return {
                "current_streak": summary["current_streak"],
                "longest_streak": summary["longest_streak"],
                "total_xp": summary["total_xp"],
                # MUHIM: `GamificationService.get_summary()` badge'larni allaqachon
                # lug'at shaklida qaytaradi ({"badge_code": "...", "earned_at": ...}) —
                # ORM obyekti emas, shuning uchun `.badge_code.value` emas, `["badge_code"]`
                # bilan o'qiladi (aks holda har safar AttributeError bilan yiqilib,
                # AI'ga doim umumiy xato matni qaytardi).
                "badges": [b["badge_code"] for b in summary["badges"]],
            }

        if tool_name == "get_today_routine":
            service = RoutineService(db)
            routine = await service.get_today(user)
            if routine is None:
                return {"routine": None}
            return {
                "routine": {
                    "morning_plan": routine.morning_plan,
                    "evening_report": routine.evening_report,
                    "status": routine.status.value,
                }
            }

        return {"error": f"Noma'lum tool: {tool_name}"}

    except FocusAIException as exc:
        # Domen xatolari (masalan, "allaqachon faol seans bor") AI'ga tushunarli
        # matn sifatida qaytariladi, u buni foydalanuvchiga o'z so'zlari bilan aytadi.
        logger.info("ai_tool_domain_error", tool=tool_name, message=exc.message)
        return {"error": exc.message}
    except Exception as exc:
        logger.error("ai_tool_execution_failed", tool=tool_name, error=str(exc))
        return {"error": "Amalni bajarishda kutilmagan xatolik yuz berdi."}
