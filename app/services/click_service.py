"""
Click Merchant API — Prepare va Complete amallarini qayta ishlash.

Click protokoli ikki bosqichli: avval `Prepare` (to'lovni tasdiqlashdan oldingi
tekshiruv), keyin `Complete` (haqiqiy to'lov tasdiqlanganda). Bu Payme'ning
CreateTransaction+PerformTransaction'iga mos keladi, lekin alohida "action"
maydoni orqali bitta endpoint'da farqlanadi.

Ikki xil to'lov maqsadi (moliyaviy javobgarlik va obuna) BITTA webhook orqali
ishlaydi — `merchant_trans_id` qiymati o'zi umumiy "reference" bo'lib,
`app.utils.payment_ref` orqali qaysi turga tegishli ekani aniqlanadi.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.click_client import ClickAction, ClickErrorCode, verify_signature
from app.models.finance import (
    CommitmentStatus,
    PaymentProvider,
    Transaction,
    TransactionPurpose,
    TransactionState,
)
from app.services.finance_service import FinanceService
from app.services.subscription_service import SubscriptionService
from app.utils.payment_ref import PaymentTargetKind, parse_payment_ref

logger = get_logger(__name__)


class ClickService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.finance = FinanceService(db)
        self.subscriptions = SubscriptionService(db)

    async def prepare(self, params: dict[str, Any]) -> dict[str, Any]:
        base_response = self._base_response(params)

        if not self._verify(params, action=ClickAction.PREPARE):
            return {
                **base_response,
                "error": ClickErrorCode.SIGN_CHECK_FAILED,
                "error_note": "Imzo mos emas",
            }

        existing = await self._get_by_click_id(params["click_trans_id"])
        if existing is not None:
            return {
                **base_response,
                "merchant_prepare_id": str(existing.id),
                "error": ClickErrorCode.SUCCESS,
                "error_note": "Success",
            }

        try:
            kind, target_id = parse_payment_ref(str(params["merchant_trans_id"]))
        except ValueError:
            return {
                **base_response,
                "error": ClickErrorCode.USER_NOT_FOUND,
                "error_note": "Noto'g'ri reference",
            }

        if kind == PaymentTargetKind.COMMITMENT:
            commitment = await self.finance.get_commitment_by_id(target_id)
            if commitment is None:
                return {
                    **base_response,
                    "error": ClickErrorCode.USER_NOT_FOUND,
                    "error_note": "Maqsad topilmadi",
                }
            if commitment.status != CommitmentStatus.PENDING_PAYMENT:
                return {
                    **base_response,
                    "error": ClickErrorCode.ALREADY_PAID,
                    "error_note": "Allaqachon to'langan",
                }
            expected_amount = commitment.amount
            purpose = TransactionPurpose.COMMITMENT
            commitment_id, subscription_id = commitment.id, None
        else:
            from app.models.subscription import PLAN_PRICES_SOM

            subscription = await self.subscriptions.get_subscription_by_id(target_id)
            if subscription is None:
                return {
                    **base_response,
                    "error": ClickErrorCode.USER_NOT_FOUND,
                    "error_note": "Obuna topilmadi",
                }
            expected_amount = Decimal(PLAN_PRICES_SOM[subscription.plan])
            purpose = TransactionPurpose.SUBSCRIPTION
            commitment_id, subscription_id = None, subscription.id

        amount_som = Decimal(params["amount"])
        if amount_som != expected_amount:
            return {
                **base_response,
                "error": ClickErrorCode.INVALID_AMOUNT,
                "error_note": "Summa mos emas",
            }

        transaction = Transaction(
            purpose=purpose,
            commitment_id=commitment_id,
            subscription_id=subscription_id,
            provider=PaymentProvider.CLICK,
            provider_transaction_id=str(params["click_trans_id"]),
            amount=amount_som,
            state=TransactionState.CREATED,
            raw_payload=params,
        )
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "click_transaction_prepared", transaction_id=str(transaction.id), purpose=purpose.value
        )

        return {
            **base_response,
            "merchant_prepare_id": str(transaction.id),
            "error": ClickErrorCode.SUCCESS,
            "error_note": "Success",
        }

    async def complete(self, params: dict[str, Any]) -> dict[str, Any]:
        base_response = self._base_response(params)

        if not self._verify(
            params,
            action=ClickAction.COMPLETE,
            merchant_prepare_id=params.get("merchant_prepare_id"),
        ):
            return {
                **base_response,
                "error": ClickErrorCode.SIGN_CHECK_FAILED,
                "error_note": "Imzo mos emas",
            }

        transaction = await self._get_by_click_id(params["click_trans_id"])
        if transaction is None:
            return {
                **base_response,
                "error": ClickErrorCode.TRANSACTION_NOT_FOUND,
                "error_note": "Tranzaksiya topilmadi",
            }

        if transaction.state == TransactionState.PERFORMED:
            return {
                **base_response,
                "merchant_confirm_id": str(transaction.id),
                "error": ClickErrorCode.SUCCESS,
                "error_note": "Success",
            }
        if transaction.state == TransactionState.CANCELLED:
            return {
                **base_response,
                "error": ClickErrorCode.TRANSACTION_CANCELLED,
                "error_note": "Tranzaksiya bekor qilingan",
            }

        click_reported_error = int(params.get("error", 0))
        if click_reported_error < 0:
            transaction.state = TransactionState.CANCELLED
            transaction.cancelled_at = datetime.now(UTC)
            await self.db.commit()

            if transaction.purpose == TransactionPurpose.COMMITMENT:
                commitment = await self.finance.get_commitment_by_id(transaction.commitment_id)
                commitment.status = CommitmentStatus.CANCELLED
                await self.db.commit()

            return {
                **base_response,
                "error": ClickErrorCode.TRANSACTION_CANCELLED,
                "error_note": "Click tomonidan bekor qilingan",
            }

        transaction.state = TransactionState.PERFORMED
        transaction.performed_at = datetime.now(UTC)
        await self.db.commit()

        if transaction.purpose == TransactionPurpose.COMMITMENT:
            commitment = await self.finance.get_commitment_by_id(transaction.commitment_id)
            await self.finance.activate_commitment(commitment, transaction)
        else:
            subscription = await self.subscriptions.get_subscription_by_id(
                transaction.subscription_id
            )
            await self.subscriptions.activate_subscription(subscription, subscription.user_id)

        logger.info("click_transaction_completed", transaction_id=str(transaction.id))

        return {
            **base_response,
            "merchant_confirm_id": str(transaction.id),
            "error": ClickErrorCode.SUCCESS,
            "error_note": "Success",
        }

    # ── Ichki yordamchi metodlar ─────────────────────────────
    def _base_response(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "click_trans_id": params.get("click_trans_id"),
            "merchant_trans_id": params.get("merchant_trans_id"),
        }

    def _verify(
        self, params: dict[str, Any], *, action: int, merchant_prepare_id: str | None = None
    ) -> bool:
        return verify_signature(
            click_trans_id=str(params["click_trans_id"]),
            service_id=str(params["service_id"]),
            merchant_trans_id=str(params["merchant_trans_id"]),
            amount=str(params["amount"]),
            action=str(action),
            sign_time=str(params["sign_time"]),
            sign_string=str(params["sign_string"]),
            merchant_prepare_id=str(merchant_prepare_id) if merchant_prepare_id else None,
        )

    async def _get_by_click_id(self, click_trans_id: str) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.provider == PaymentProvider.CLICK,
                Transaction.provider_transaction_id == str(click_trans_id),
            )
        )
        return result.scalar_one_or_none()
