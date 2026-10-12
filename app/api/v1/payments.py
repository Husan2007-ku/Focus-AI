"""
Payme webhook endpoint'i.

Payme bizning serverimizga to'g'ridan-to'g'ri (foydalanuvchi autentifikatsiyasisiz)
HTTP Basic Auth orqali murojaat qiladi: username="Paycom", password=merchant key.
Shuning uchun bu endpoint `get_current_user`dan FOYDALANMAYDI — o'zining alohida
autentifikatsiya usuli bor.
"""

import base64
import binascii
import secrets
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.services.click_service import ClickService
from app.services.payme_service import PaymeRPCError, PaymeService

logger = get_logger(__name__)
router = APIRouter()

METHOD_MAP = {
    "CheckPerformTransaction": "check_perform_transaction",
    "CreateTransaction": "create_transaction",
    "PerformTransaction": "perform_transaction",
    "CancelTransaction": "cancel_transaction",
    "CheckTransaction": "check_transaction",
    "GetStatement": "get_statement",
}

INSUFFICIENT_PRIVILEGE_CODE = -32504


def _verify_payme_auth(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(authorization.removeprefix("Basic ")).decode()
        username, _, password = decoded.partition(":")
    except (binascii.Error, ValueError):
        return False

    return username == "Paycom" and secrets.compare_digest(password, settings.PAYME_SECRET_KEY)


@router.post("/webhooks/payme")
@limiter.limit("60/minute")
async def payme_webhook(
    request: Request, authorization: str | None = Header(default=None)
) -> JSONResponse:
    body: dict[str, Any] = await request.json()
    request_id = body.get("id")

    if not _verify_payme_auth(authorization):
        logger.warning("payme_webhook_unauthorized")
        return JSONResponse(
            {
                "error": {
                    "code": INSUFFICIENT_PRIVILEGE_CODE,
                    "message": {
                        "uz": "Ruxsat yo'q.",
                        "ru": "Недостаточно прав.",
                        "en": "Insufficient privilege.",
                    },
                },
                "id": request_id,
            }
        )

    method_name = body.get("method")
    service_method = METHOD_MAP.get(method_name)

    if service_method is None:
        return JSONResponse(
            {
                "error": {
                    "code": -32601,
                    "message": {
                        "uz": "Metod topilmadi.",
                        "ru": "Метод не найден.",
                        "en": "Method not found.",
                    },
                },
                "id": request_id,
            }
        )

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        service = PaymeService(db)
        try:
            result = await getattr(service, service_method)(body.get("params", {}))
            return JSONResponse({"result": result, "id": request_id})
        except PaymeRPCError as exc:
            logger.warning(
                "payme_rpc_error", method=method_name, code=exc.code, message=exc.message
            )
            return JSONResponse(
                {
                    "error": {
                        "code": exc.code,
                        "message": {"uz": exc.message, "ru": exc.message, "en": exc.message},
                    },
                    "id": request_id,
                }
            )
        # kutilmagan xato — Payme'ga umumiy xato qaytariladi, batafsili ichki logga yoziladi
        except Exception as exc:
            logger.error("payme_webhook_unhandled_error", method=method_name, error=str(exc))
            return JSONResponse(
                {
                    "error": {
                        "code": -32400,
                        "message": {
                            "uz": "Ichki xatolik.",
                            "ru": "Внутренняя ошибка.",
                            "en": "Internal error.",
                        },
                    },
                    "id": request_id,
                }
            )


@router.post("/webhooks/click")
@limiter.limit("60/minute")
async def click_webhook(request: Request) -> JSONResponse:
    """
    Click `Prepare` va `Complete` amallarini bitta endpoint orqali yuboradi —
    `action` maydoni (0=Prepare, 1=Complete) qaysi bosqich ekanini bildiradi.
    Click form-encoded (application/x-www-form-urlencoded) so'rov yuboradi.
    """
    form = await request.form()
    params = dict(form)

    action = int(params.get("action", -1))

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        service = ClickService(db)
        try:
            if action == 0:
                result = await service.prepare(params)
            elif action == 1:
                result = await service.complete(params)
            else:
                result = {
                    "click_trans_id": params.get("click_trans_id"),
                    "merchant_trans_id": params.get("merchant_trans_id"),
                    "error": -3,
                    "error_note": "Noma'lum action",
                }
            return JSONResponse(result)
        except Exception as exc:
            logger.error("click_webhook_unhandled_error", action=action, error=str(exc))
            return JSONResponse(
                {
                    "click_trans_id": params.get("click_trans_id"),
                    "merchant_trans_id": params.get("merchant_trans_id"),
                    "error": -8,
                    "error_note": "Ichki xatolik",
                }
            )
