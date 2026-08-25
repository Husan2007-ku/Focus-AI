"""
AI Agent biznes logikasi: suhbatlarni boshqarish, xabarlarni saqlash,
kunlik so'rov limitini nazorat qilish (cost governance), va Claude'ning
tool-use (agentic) rejimini boshqarish.
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.integrations.claude_client import claude_client, extract_text
from app.models.ai_chat import AIConversation, AIMessage, MessageRole
from app.models.user import SubscriptionTier, User
from app.services.ai_tools import TOOL_DEFINITIONS, execute_tool

logger = get_logger(__name__)

MAX_HISTORY_MESSAGES = 20  # Claude'ga yuboriladigan kontekst chegarasi (token xarajatini nazorat qilish uchun)
MAX_TOOL_ITERATIONS = 5  # cheksiz tool-chaqiruv siklidan himoya


class AIService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def chat(self, user: User, message: str, conversation_id: uuid.UUID | None) -> tuple[uuid.UUID, str]:
        await self._enforce_daily_limit(user)

        conversation = await self._get_or_create_conversation(user, conversation_id)

        user_message = AIMessage(
            conversation_id=conversation.id, role=MessageRole.USER, content=message
        )
        self.db.add(user_message)
        await self.db.commit()

        history = await self._build_history(conversation.id)
        reply_text = await self._run_agent_loop(history, user)

        assistant_message = AIMessage(
            conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=reply_text
        )
        self.db.add(assistant_message)

        if conversation.title is None:
            conversation.title = message[:80]

        await self.db.commit()

        logger.info("ai_chat_completed", user_id=str(user.id), conversation_id=str(conversation.id))
        return conversation.id, reply_text

    async def get_conversation(self, user: User, conversation_id: uuid.UUID) -> AIConversation:
        result = await self.db.execute(
            select(AIConversation)
            .options(selectinload(AIConversation.messages))
            .where(AIConversation.id == conversation_id, AIConversation.user_id == user.id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise NotFoundError("Suhbat topilmadi.")
        return conversation

    async def list_conversations(self, user: User) -> list[AIConversation]:
        result = await self.db.execute(
            select(AIConversation)
            .where(AIConversation.user_id == user.id)
            .order_by(AIConversation.updated_at.desc())
        )
        return list(result.scalars().all())

    # ── Agentic (tool-use) loop ──────────────────────────────
    async def _run_agent_loop(self, history: list[dict], user: User) -> str:
        """
        Claude'ga xabarlarni yuboradi; agar u tool chaqirishni so'rasa, tegishli
        amalni bajarib, natijani qaytadan Claude'ga beradi — bu shuncha marta
        takrorlanadiki, Claude yakuniy matn javob bergunicha (yoki chegaraga
        yetgunicha, cheksiz sikldan himoya sifatida).
        """
        messages = list(history)  # asl tarixni o'zgartirmaslik uchun nusxa

        for _ in range(MAX_TOOL_ITERATIONS):
            response = await claude_client.create_message(messages, tools=TOOL_DEFINITIONS)

            if response.stop_reason != "tool_use":
                return extract_text(response)

            # Claude'ning tool so'rovini (matn + tool_use bloklari) tarixga qo'shamiz.
            assistant_blocks = [block.model_dump() for block in response.content]
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await execute_tool(block.name, block.input, self.db, user)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        logger.warning("ai_agent_max_iterations_reached", user_id=str(user.id))
        return "Kechirasiz, so'rovingizni to'liq bajara olmadim. Iltimos, aniqroq qilib qayta so'rab ko'ring."

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _enforce_daily_limit(self, user: User) -> None:
        limit = (
            settings.AI_DAILY_REQUEST_LIMIT_FREE
            if user.subscription_tier == SubscriptionTier.FREE
            else settings.AI_DAILY_REQUEST_LIMIT_PREMIUM
        )

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"ai:daily_count:{user.id}:{today}"

        current_count = await redis_client.incr(key)
        if current_count == 1:
            await redis_client.expire(key, 26 * 60 * 60)  # ~1 kun + zaxira vaqt

        if current_count > limit:
            raise RateLimitError(
                f"Kunlik AI so'rovlar limiti ({limit}) tugadi. Ertaga qayta urinib ko'ring "
                "yoki Premium'ga o'ting."
            )

    async def _get_or_create_conversation(
        self, user: User, conversation_id: uuid.UUID | None
    ) -> AIConversation:
        if conversation_id is not None:
            result = await self.db.execute(
                select(AIConversation).where(
                    AIConversation.id == conversation_id, AIConversation.user_id == user.id
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation is None:
                raise NotFoundError("Suhbat topilmadi.")
            return conversation

        conversation = AIConversation(user_id=user.id)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def _build_history(self, conversation_id: uuid.UUID) -> list[dict[str, str]]:
        result = await self.db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
        messages = list(reversed(result.scalars().all()))
        return [{"role": m.role.value, "content": m.content} for m in messages]
