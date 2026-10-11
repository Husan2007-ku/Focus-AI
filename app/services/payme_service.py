"""
Payme Merchant API — JSON-RPC webhook metodlarini qayta ishlash.

Rasmiy protokol: https://developer.help.paycom.uz/
Bu servis Payme'ning bizga yuboradigan har bir metodini ishlaydi va
FinanceService/SubscriptionService orqali domen o'zgarishlarini amalga oshiradi.

MUHIM — IDEMPOTENTLIK: Payme tarmoq muammolari tufayli bir xil so'rovni
qayta yuborishi mumkin. Shuning uchun CreateTransaction/PerformTransaction/
CancelTransaction — barchasi "allaqachon bajarilgan bo'lsa, xuddi shu
natijani qaytarish" tamoyiliga amal qiladi (yangi effekt yaratmaydi).

Ikki xil to'lov maqsadi (moliyaviy javobgarlik va obuna) BITTA webhook
orqali ishlaydi — `params["account"]["ref"]` qiymati
(`app.utils.payment_ref`) orqali qaysi turga tegishli ekani aniqlanadi.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.payme_client import PaymeErrorCode
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

# Payme'ning o'z raqamli holat kodlari (bizning TransactionState'dan farqli,
# ularning protokoliga xos)
PAYME_STATE_CREATED = 1
PAYME_STATE_PERFORMED = 2
PAYME_STATE_CANCELLED_AFTER_CREATE = -1
PAYME_STATE_CANCELLED_AFTER_PERFORM = -2


class PaymeRPCError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _to_millis(dt: datetime | None) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp() * 1000)


class PaymeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.finance = FinanceService(db)
        self.subscriptions = SubscriptionService(db)

    async def check_perform_transaction(self, params: dict[str, Any]) -> dict[str, Any]:
        kind, target = await self._resolve_target(params)
        amount_som = Decimal(params["amount"]) / 100

        if kind == PaymentTargetKind.COMMITMENT:
            if target.status != CommitmentStatus.PENDING_PAYMENT:
                raise PaymeRPCError(
                    PaymeErrorCode.UNABLE_TO_PERFORM_OPERATION,
                    "Bu maqsad uchun to'lov allaqachon qabul qilingan.",
                )
            expected_amount = target.amount
        else:
            from app.models.subscription import PLAN_PRICES_SOM

            expected_amount = Decimal(PLAN_PRICES_SOM[target.plan])

        if amount_som != expected_amount:
            raise PaymeRPCError(PaymeErrorCode.INVALID_AMOUNT, "Summa mos kelmadi.")

        return {"allow": True}

    async def create_transaction(self, params: dict[str, Any]) -> dict[str, Any]:
        provider_tx_id = params["id"]
        existing = await self._get_by_provider_id(provider_tx_id)

        if existing is not None:
            return {
                "create_time": _to_millis(existing.created_at),
                "transaction": str(existing.id),
                "state": self._to_payme_state(existing),
            }

        kind, target = await self._resolve_target(params)
        amount_som = Decimal(params["amount"]) / 100

        if kind == PaymentTargetKind.COMMITMENT:
            if target.status != CommitmentStatus.PENDING_PAYMENT:
                raise PaymeRPCError(
                    PaymeErrorCode.UNABLE_TO_PERFORM_OPERATION,
                    "Bu maqsad uchun to'lov allaqachon qabul qilingan.",
                )
            purpose = TransactionPurpose.COMMITMENT
            commitment_id, subscription_id = target.id, None
        else:
            from app.models.subscription import PLAN_PRICES_SOM

            if amount_som != Decimal(PLAN_PRICES_SOM[target.plan]):
                raise PaymeRPCError(PaymeErrorCode.INVALID_AMOUNT, "Summa mos kelmadi.")
            purpose = TransactionPurpose.SUBSCRIPTION
            commitment_id, subscription_id = None, target.id

        transaction = Transaction(
            purpose=purpose,
            commitment_id=commitment_id,
            subscription_id=subscription_id,
            provider=PaymentProvider.PAYME,
            provider_transaction_id=provider_tx_id,
            amount=amount_som,
            state=TransactionState.CREATED,
            raw_payload=params,
        )
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "payme_transaction_created", transaction_id=str(transaction.id), purpose=purpose.value
        )

        return {
            "create_time": _to_millis(transaction.created_at),
            "transaction": str(transaction.id),
            "state": PAYME_STATE_CREATED,
        }

    async def perform_transaction(self, params: dict[str, Any]) -> dict[str, Any]:
        transaction = await self._get_by_provider_id_or_raise(params["id"])

        if transaction.state == TransactionState.PERFORMED:
            return {
                "transaction": str(transaction.id),
                "perform_time": _to_millis(transaction.performed_at),
                "state": PAYME_STATE_PERFORMED,
            }

        if transaction.state != TransactionState.CREATED:
            raise PaymeRPCError(
                PaymeErrorCode.UNABLE_TO_PERFORM_OPERATION, "Tranzaksiya holati mos emas."
            )

        transaction.state = TransactionState.PERFORMED
        transaction.performed_at = datetime.now(UTC)
        await self.db.commit()

        await self._activate(transaction)

        return {
            "transaction": str(transaction.id),
            "perform_time": _to_millis(transaction.performed_at),
            "state": PAYME_STATE_PERFORMED,
        }

    async def cancel_transaction(self, params: dict[str, Any]) -> dict[str, Any]:
        transaction = await self._get_by_provider_id_or_raise(params["id"])

        if transaction.state == TransactionState.CANCELLED:
            return {
                "transaction": str(transaction.id),
                "cancel_time": _to_millis(transaction.cancelled_at),
                "state": self._to_payme_state(transaction),
            }

        was_performed = transaction.state == TransactionState.PERFORMED

        transaction.state = TransactionState.CANCELLED
        transaction.cancelled_at = datetime.now(UTC)
        await self.db.commit()

        if was_performed:
            await self._reverse(transaction)
        elif transaction.purpose == TransactionPurpose.COMMITMENT:
            commitment = await self.finance.get_commitment_by_id(transaction.commitment_id)
            commitment.status = CommitmentStatus.CANCELLED
            await self.db.commit()

        return {
            "transaction": str(transaction.id),
            "cancel_time": _to_millis(transaction.cancelled_at),
            "state": (
                PAYME_STATE_CANCELLED_AFTER_PERFORM
                if was_performed
                else PAYME_STATE_CANCELLED_AFTER_CREATE
            ),
        }

    async def check_transaction(self, params: dict[str, Any]) -> dict[str, Any]:
        transaction = await self._get_by_provider_id_or_raise(params["id"])
        return {
            "create_time": _to_millis(transaction.created_at),
            "perform_time": _to_millis(transaction.performed_at),
            "cancel_time": _to_millis(transaction.cancelled_at),
            "transaction": str(transaction.id),
            "state": self._to_payme_state(transaction),
            "reason": None,
        }

    async def get_statement(self, params: dict[str, Any]) -> dict[str, Any]:
        from_dt = datetime.fromtimestamp(params["from"] / 1000, tz=UTC)
        to_dt = datetime.fromtimestamp(params["to"] / 1000, tz=UTC)

        result = await self.db.execute(
            select(Transaction).where(
                Transaction.provider == PaymentProvider.PAYME,
                Transaction.created_at >= from_dt,
                Transaction.created_at <= to_dt,
            )
        )
        transactions = list(result.scalars().all())

        return {
            "transactions": [
                {
                    "id": t.provider_transaction_id,
                    "time": _to_millis(t.created_at),
                    "amount": int(t.amount * 100),
                    "create_time": _to_millis(t.created_at),
                    "perform_time": _to_millis(t.performed_at),
                    "cancel_time": _to_millis(t.cancelled_at),
                    "transaction": str(t.id),
                    "state": self._to_payme_state(t),
                    "reason": None,
                }
                for t in transactions
            ]
        }

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _resolve_target(self, params: dict[str, Any]):
        account = params.get("account", {})
        ref = account.get("ref")

        if not ref:
            raise PaymeRPCError(PaymeErrorCode.INVALID_ACCOUNT_FIELD, "ref ko'rsatilmagan.")

        try:
            kind, target_id = parse_payment_ref(ref)
        except ValueError as exc:
            raise PaymeRPCError(PaymeErrorCode.INVALID_ACCOUNT_FIELD, str(exc)) from exc

        if kind == PaymentTargetKind.COMMITMENT:
            target = await self.finance.get_commitment_by_id(target_id)
        else:
            target = await self.subscriptions.get_subscription_by_id(target_id)

        if target is None:
            raise PaymeRPCError(PaymeErrorCode.ACCOUNT_NOT_FOUND, "To'lov maqsadi topilmadi.")

        return kind, target

    async def _activate(self, transaction: Transaction) -> None:
        if transaction.purpose == TransactionPurpose.COMMITMENT:
            commitment = await self.finance.get_commitment_by_id(transaction.commitment_id)
            await self.finance.activate_commitment(commitment, transaction)
        else:
            subscription = await self.subscriptions.get_subscription_by_id(
                transaction.subscription_id
            )
            await self.subscriptions.activate_subscription(subscription, subscription.user_id)

    async def _reverse(self, transaction: Transaction) -> None:
        if transaction.purpose == TransactionPurpose.COMMITMENT:
            commitment = await self.finance.get_commitment_by_id(transaction.commitment_id)
            await self.finance.reverse_deposit(commitment, transaction)
        else:
            subscription = await self.subscriptions.get_subscription_by_id(
                transaction.subscription_id
            )
            await self.subscriptions.deactivate_subscription(subscription)

    async def _get_by_provider_id(self, provider_tx_id: str) -> Transaction | None:
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.provider == PaymentProvider.PAYME,
                Transaction.provider_transaction_id == provider_tx_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_by_provider_id_or_raise(self, provider_tx_id: str) -> Transaction:
        transaction = await self._get_by_provider_id(provider_tx_id)
        if transaction is None:
            raise PaymeRPCError(PaymeErrorCode.TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi.")
        return transaction

    def _to_payme_state(self, transaction: Transaction) -> int:
        if transaction.state == TransactionState.CREATED:
            return PAYME_STATE_CREATED
        if transaction.state == TransactionState.PERFORMED:
            return PAYME_STATE_PERFORMED
        return (
            PAYME_STATE_CANCELLED_AFTER_PERFORM
            if transaction.performed_at is not None
            else PAYME_STATE_CANCELLED_AFTER_CREATE
        )
