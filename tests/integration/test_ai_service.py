"""AIService uchun testlar — suhbat saqlash, kunlik limit (cost governance)
va Claude bilan agentic (tool-use) sikl.

`claude_client.create_message` tashqi Anthropic API chaqiruvi qiladi —
shuning uchun monkeypatch bilan almashtiriladi (haqiqiy Claude key kerak
emas). `execute_tool` esa real DB bilan ishlaydigan haqiqiy tool'lardan
foydalanadi (`get_today_routine` kabi) — alohida mock qilinmaydi, chunki
u allaqachon `test_ai_tools.py`da sinalgan.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, RateLimitError
from app.models.user import AuthProvider, SubscriptionTier, User
from app.services.ai_service import MAX_TOOL_ITERATIONS, AIService


class _FakeBlock:
    """`anthropic.types.Message`ning content blokini (text yoki tool_use)
    yetarlicha taqlid qiladi — AIService faqat shu maydonlarni o'qiydi."""

    def __init__(
        self,
        *,
        type: str,
        text: str = "",
        name: str = "",
        input: dict | None = None,
        id: str = "",
    ) -> None:
        self.type = type
        self.text = text
        self.name = name
        self.input = input or {}
        self.id = id

    def model_dump(self) -> dict:
        return {
            "type": self.type,
            "text": self.text,
            "name": self.name,
            "input": self.input,
            "id": self.id,
        }


class _FakeMessage:
    def __init__(self, *, stop_reason: str, content: list[_FakeBlock]) -> None:
        self.stop_reason = stop_reason
        self.content = content


def _text_reply(text: str) -> _FakeMessage:
    return _FakeMessage(stop_reason="end_turn", content=[_FakeBlock(type="text", text=text)])


def _tool_call(
    name: str, tool_use_id: str = "tool-1", tool_input: dict | None = None
) -> _FakeMessage:
    return _FakeMessage(
        stop_reason="tool_use",
        content=[_FakeBlock(type="tool_use", name=name, input=tool_input or {}, id=tool_use_id)],
    )


@pytest.mark.asyncio
async def test_chat_creates_conversation_and_returns_reply(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Salom! Bugun qanday yordam bera olaman?")),
    )

    conversation_id, reply = await AIService(db_session).chat(test_user, "Salom", None)

    assert reply == "Salom! Bugun qanday yordam bera olaman?"
    conversation = await AIService(db_session).get_conversation(test_user, conversation_id)
    assert len(conversation.messages) == 2
    assert conversation.title == "Salom"


@pytest.mark.asyncio
async def test_chat_continues_existing_conversation(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )
    service = AIService(db_session)

    conversation_id, _ = await service.chat(test_user, "Birinchi xabar", None)
    second_id, _ = await service.chat(test_user, "Ikkinchi xabar", conversation_id)

    assert second_id == conversation_id
    conversation = await service.get_conversation(test_user, conversation_id)
    assert len(conversation.messages) == 4


@pytest.mark.asyncio
async def test_chat_raises_not_found_for_unknown_conversation_id(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )

    with pytest.raises(NotFoundError):
        await AIService(db_session).chat(test_user, "Salom", uuid.uuid4())


@pytest.mark.asyncio
async def test_chat_enforces_daily_limit_for_free_tier(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )
    service = AIService(db_session)

    for _ in range(3):  # AI_DAILY_REQUEST_LIMIT_FREE = 3 (standart sozlama)
        await service.chat(test_user, "Savol", None)

    with pytest.raises(RateLimitError):
        await service.chat(test_user, "Yana bir savol", None)


@pytest.mark.asyncio
async def test_chat_premium_tier_is_not_blocked_by_free_limit(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_user.subscription_tier = SubscriptionTier.PREMIUM
    await db_session.commit()
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )
    service = AIService(db_session)

    for _ in range(4):  # FREE limitidan (3) ko'p, lekin PREMIUM uchun muammo emas
        await service.chat(test_user, "Savol", None)


@pytest.mark.asyncio
async def test_agent_loop_executes_tool_then_returns_final_text(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_create = AsyncMock(
        side_effect=[
            _tool_call("get_today_routine"),
            _text_reply("Bugun rejangiz yo'q ekan."),
        ]
    )
    monkeypatch.setattr("app.services.ai_service.claude_client.create_message", mock_create)

    _, reply = await AIService(db_session).chat(test_user, "Bugungi rejam qanday?", None)

    assert reply == "Bugun rejangiz yo'q ekan."
    assert mock_create.await_count == 2


@pytest.mark.asyncio
async def test_agent_loop_gives_up_after_max_iterations(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_create = AsyncMock(return_value=_tool_call("get_today_routine"))
    monkeypatch.setattr("app.services.ai_service.claude_client.create_message", mock_create)

    _, reply = await AIService(db_session).chat(test_user, "Takrorlanuvchi tool chaqiruvi", None)

    assert "to'liq bajara olmadim" in reply
    assert mock_create.await_count == MAX_TOOL_ITERATIONS


@pytest.mark.asyncio
async def test_get_conversation_raises_not_found_for_other_users_conversation(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )
    service = AIService(db_session)
    conversation_id, _ = await service.chat(test_user, "Mening xabarim", None)

    other_user = User(
        phone_number=f"+998905{uuid.uuid4().int % 1_000_000:06d}",
        primary_auth_provider=AuthProvider.PHONE,
    )
    db_session.add(other_user)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await service.get_conversation(other_user, conversation_id)


@pytest.mark.asyncio
async def test_list_conversations_returns_only_users_own_conversations(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.claude_client.create_message",
        AsyncMock(return_value=_text_reply("Javob")),
    )
    service = AIService(db_session)
    await service.chat(test_user, "Birinchi suhbat", None)
    await service.chat(test_user, "Ikkinchi suhbat", None)

    conversations = await service.list_conversations(test_user)

    assert len(conversations) == 2
    assert all(c.user_id == test_user.id for c in conversations)
