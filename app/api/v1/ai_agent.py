"""
AI Agent endpoint'lari.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import (
    ChatRequestSchema,
    ChatResponseSchema,
    ConversationDetailSchema,
    ConversationResponseSchema,
)
from app.services.ai_service import AIService

router = APIRouter()


@router.post("/chat", response_model=ChatResponseSchema)
async def chat(
    payload: ChatRequestSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponseSchema:
    """
    AI yordamchiga xabar yuboradi. `conversation_id` berilmasa, yangi suhbat
    boshlanadi. Kunlik so'rov limiti tarifga qarab qo'llaniladi.
    """
    service = AIService(db)
    conversation_id, reply = await service.chat(
        current_user, payload.message, payload.conversation_id
    )
    return ChatResponseSchema(conversation_id=conversation_id, reply=reply)


@router.get("/conversations", response_model=list[ConversationResponseSchema])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponseSchema]:
    """Foydalanuvchining barcha suhbatlari ro'yxati (oxirgi faollik bo'yicha)."""
    service = AIService(db)
    conversations = await service.list_conversations(current_user)
    return [ConversationResponseSchema.model_validate(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailSchema)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailSchema:
    """Bitta suhbatning to'liq xabarlar tarixi."""
    service = AIService(db)
    conversation = await service.get_conversation(current_user, conversation_id)
    return ConversationDetailSchema.model_validate(conversation)
