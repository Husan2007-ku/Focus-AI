"""
AI Agent endpoint'lari uchun request/response sxemalari.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.ai_chat import MessageRole


class ChatRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Mavjud suhbatni davom ettirish uchun; bo'sh bo'lsa — yangi suhbat boshlanadi",
    )


class ChatResponseSchema(BaseModel):
    conversation_id: uuid.UUID
    reply: str


class MessageResponseSchema(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponseSchema(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailSchema(ConversationResponseSchema):
    messages: list[MessageResponseSchema]
