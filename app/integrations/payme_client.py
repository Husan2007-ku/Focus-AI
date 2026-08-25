"""
Payme integratsiyasi — checkout URL generatsiyasi va JSON-RPC xato kodlari.

Payme protokoli ikki tomonlama ishlaydi:
1. Biz foydalanuvchini checkout.paycom.uz sahifasiga yo'naltiramiz (shu yerda
   URL generatsiya qilinadi).
2. Payme to'lov holatini bizning webhook'imizga JSON-RPC so'rovlari orqali
   xabar qiladi (bu `services/payme_service.py`da ishlanadi).
"""

import base64

from app.core.config import settings


class PaymeErrorCode:
    """Payme Merchant API standart xato kodlari (protokol spetsifikatsiyasi bo'yicha)."""

    INVALID_AMOUNT = -31001
    TRANSACTION_NOT_FOUND = -31003
    UNABLE_TO_PERFORM_OPERATION = -31008
    ACCOUNT_NOT_FOUND = -31050
    INVALID_ACCOUNT_FIELD = -31051


def generate_checkout_url(ref: str, amount_som: float) -> str:
    """
    Payme checkout sahifasiga yo'naltiruvchi URL yaratadi.
    Summa Payme uchun TIYIN'da yuborilishi kerak (1 so'm = 100 tiyin).
    `ref` — `app.utils.payment_ref.build_payment_ref()` orqali hosil qilingan
    umumiy to'lov identifikatori (masalan, "commitment:<uuid>").
    """
    amount_tiyin = int(round(amount_som * 100))
    params = f"m={settings.PAYME_MERCHANT_ID};ac.ref={ref};a={amount_tiyin}"
    encoded = base64.b64encode(params.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"
