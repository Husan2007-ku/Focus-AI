"""
Click integratsiyasi — checkout URL generatsiyasi va imzo (sign_string) tekshiruvi.

Click protokoli Payme'dan farqli — JSON-RPC emas, oddiy POST (form-encoded)
so'rovlar orqali ishlaydi va har bir so'rov MD5 asosidagi `sign_string` bilan
tasdiqlanadi. Https://docs.click.uz/ (Merchant API) spetsifikatsiyasiga mos.
"""

import hashlib

from app.core.config import settings


class ClickAction:
    PREPARE = 0
    COMPLETE = 1


class ClickErrorCode:
    SUCCESS = 0
    SIGN_CHECK_FAILED = -1
    INVALID_AMOUNT = -2
    ACTION_NOT_FOUND = -3
    ALREADY_PAID = -4
    USER_NOT_FOUND = -5  # bizda — commitment topilmadi
    TRANSACTION_NOT_FOUND = -6
    FAILED_TO_UPDATE = -7
    ERROR_IN_REQUEST = -8
    TRANSACTION_CANCELLED = -9


def generate_checkout_url(ref: str, amount_som: float) -> str:
    """
    Click checkout sahifasiga yo'naltiruvchi URL. Click summani SO'MDA kutadi (tiyin emas).
    `ref` — `app.utils.payment_ref.build_payment_ref()` orqali hosil qilingan
    umumiy to'lov identifikatori; Click buni `merchant_trans_id` sifatida qaytaradi.
    """
    return (
        "https://my.click.uz/services/pay"
        f"?service_id={settings.CLICK_SERVICE_ID}"
        f"&merchant_id={settings.CLICK_MERCHANT_ID}"
        f"&amount={amount_som}"
        f"&transaction_param={ref}"
    )


def verify_signature(
    *,
    click_trans_id: str,
    service_id: str,
    merchant_trans_id: str,
    amount: str,
    action: str,
    sign_time: str,
    sign_string: str,
    merchant_prepare_id: str | None = None,
) -> bool:
    """
    Click'ning `sign_string` maydonini qayta hisoblab, kelgan qiymat bilan
    solishtiradi. Ketma-ketlik va formatga Click spetsifikatsiyasi talablari
    bo'yicha qat'iy amal qilinishi shart — aks holda barcha imzolar mos kelmaydi.
    """
    if merchant_prepare_id is not None:
        raw = (
            f"{click_trans_id}{service_id}{settings.CLICK_SECRET_KEY}{merchant_trans_id}"
            f"{merchant_prepare_id}{amount}{action}{sign_time}"
        )
    else:
        raw = (
            f"{click_trans_id}{service_id}{settings.CLICK_SECRET_KEY}{merchant_trans_id}"
            f"{amount}{action}{sign_time}"
        )

    expected = hashlib.md5(raw.encode()).hexdigest()
    return expected == sign_string
