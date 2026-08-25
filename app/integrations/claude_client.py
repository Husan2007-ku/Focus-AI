"""
Claude (Anthropic) API integratsiyasi.

Cost-governance eslatmasi: bu klass faqat API chaqiruvini bajaradi.
Kunlik so'rov limiti va keshlash — `AIService` qatlamida amalga oshiriladi,
shunda bu klass sof va qayta ishlatiladigan bo'lib qoladi.

Tool-use qo'llab-quvvatlash: `create_message()` xom Anthropic javobini
qaytaradi (faqat matn emas), shunda chaqiruvchi tomon `stop_reason`ni
tekshirib, tool chaqiruvlarini agentic loop orqali qayta ishlashi mumkin
(qarang: `app/services/ai_service.py`).
"""

from typing import Any

from anthropic import APIError, AsyncAnthropic
from anthropic.types import Message

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """Sen FocusAI ilovasining shaxsiy AI yordamchisisiz.
Vazifang — foydalanuvchiga diqqatini jamlashda, kunlik rejalashtirishda va
o'z maqsadlariga erishishda yordam berish.

Qoidalar:
- Har doim o'zbek tilida, iliq va qo'llab-quvvatlovchi ohangda javob ber.
- Javoblaring qisqa va amaliy bo'lsin — uzun ma'ruza o'qima.
- Foydalanuvchini ayblama yoki uyaltirma, buning o'rniga kichik va aniq
  qadamlar taklif qil.
- Senda foydalanuvchi nomidan haqiqiy amallarni bajaradigan tool'lar bor
  (fokus seansi boshlash, statistika ko'rish va h.k.). Agar foydalanuvchi
  aniq parametr (masalan, davomiylik) aytmagan bo'lsa, taxmin qilmasdan
  undan so'ra.
- Agar foydalanuvchi mavzudan chetga chiqsa (masalan tibbiy yoki huquqiy
  maslahat so'rasa), buni ilova doirasidan tashqarida ekanini ayt va
  mutaxassisga murojaat qilishni tavsiya qil.
"""


class ClaudeClient:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Xom Anthropic Message obyektini qaytaradi (tool-use tekshiruvi uchun kerak)."""
        try:
            kwargs: dict[str, Any] = {
                "model": settings.AI_MODEL,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            return await self._client.messages.create(**kwargs)
        except APIError as exc:
            logger.error("claude_api_error", error=str(exc))
            raise ExternalServiceError(
                "AI yordamchi bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring."
            ) from exc

    async def send_message(self, conversation_history: list[dict[str, str]]) -> str:
        """Oddiy (tool'siz) chaqiruv — faqat matn javobini qaytaradi. Masalan, kunlik AI fikri uchun."""
        response = await self.create_message(conversation_history)
        return extract_text(response)


def extract_text(response: Message) -> str:
    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "".join(text_blocks)


claude_client = ClaudeClient()
