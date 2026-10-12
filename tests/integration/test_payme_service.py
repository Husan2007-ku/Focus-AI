"""PaymeService uchun testlar — JSON-RPC webhook metodlari va idempotentlik.

Payme'da ham tashqi HTTP chaqiruvi yo'q (checkout URL — base64 bilan string
kodlash), shuning uchun mock kerak emas — haqiqiy DB bilan ishlaydi.
Summalar Payme protokoli bo'yicha TIYIN'da yuboriladi (1 so'm = 100 tiyin).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.payme_client import PaymeErrorCode
from app.models.finance import CommitmentStatus, FinancialCommitment
from app.models.subscription import PLAN_PRICES_SOM, Subscription, SubscriptionPlan
from app.models.user import User
from app.services.payme_service import (
    PAYME_STATE_CANCELLED_AFTER_CREATE,
    PAYME_STATE_CANCELLED_AFTER_PERFORM,
    PAYME_STATE_CREATED,
    PAYME_STATE_PERFORMED,
    PaymeRPCError,
    PaymeService,
)
from app.utils.payment_ref import PaymentTargetKind, build_payment_ref


async def _make_commitment(
    db_session: AsyncSession, user: User, amount: str = "50000"
) -> FinancialCommitment:
    commitment = FinancialCommitment(
        user_id=user.id,
        goal_description="Haftasiga 10 soat fokus",
        amount=Decimal(amount),
        target_focus_minutes=600,
        deadline=datetime.now(UTC) + timedelta(days=7),
        status=CommitmentStatus.PENDING_PAYMENT,
    )
    db_session.add(commitment)
    await db_session.commit()
    await db_session.refresh(commitment)
    return commitment


async def _make_subscription(
    db_session: AsyncSession, user: User, plan: SubscriptionPlan = SubscriptionPlan.MONTHLY
) -> Subscription:
    now = datetime.now(UTC)
    subscription = Subscription(
        user_id=user.id,
        plan=plan,
        starts_at=now,
        expires_at=now + timedelta(days=30),
        is_active=False,
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)
    return subscription


@pytest.mark.asyncio
async def test_check_perform_transaction_allows_valid_commitment_payment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"account": {"ref": ref}, "amount": 50000 * 100}

    result = await PaymeService(db_session).check_perform_transaction(params)

    assert result == {"allow": True}


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_amount_mismatch(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"account": {"ref": ref}, "amount": 1 * 100}

    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).check_perform_transaction(params)

    assert exc_info.value.code == PaymeErrorCode.INVALID_AMOUNT


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_unknown_ref(
    db_session: AsyncSession, test_user: User
) -> None:
    params = {"account": {"ref": "commitment:" + str(uuid.uuid4())}, "amount": 50000 * 100}

    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).check_perform_transaction(params)

    assert exc_info.value.code == PaymeErrorCode.ACCOUNT_NOT_FOUND


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_missing_ref_field(
    db_session: AsyncSession, test_user: User
) -> None:
    params = {"account": {}, "amount": 50000 * 100}

    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).check_perform_transaction(params)

    assert exc_info.value.code == PaymeErrorCode.INVALID_ACCOUNT_FIELD


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_already_paid_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    commitment.status = CommitmentStatus.ACTIVE
    await db_session.commit()
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"account": {"ref": ref}, "amount": 50000 * 100}

    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).check_perform_transaction(params)

    assert exc_info.value.code == PaymeErrorCode.UNABLE_TO_PERFORM_OPERATION


@pytest.mark.asyncio
async def test_create_transaction_creates_new_transaction_for_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"id": "payme-tx-1", "account": {"ref": ref}, "amount": 50000 * 100}

    result = await PaymeService(db_session).create_transaction(params)

    assert result["state"] == PAYME_STATE_CREATED
    assert "transaction" in result


@pytest.mark.asyncio
async def test_create_transaction_is_idempotent_for_same_provider_id(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"id": "payme-tx-2", "account": {"ref": ref}, "amount": 50000 * 100}
    service = PaymeService(db_session)

    first = await service.create_transaction(params)
    second = await service.create_transaction(params)

    assert first["transaction"] == second["transaction"]


@pytest.mark.asyncio
async def test_create_transaction_handles_concurrent_duplicate_via_db_constraint(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Race-condition regressiya testi (2026-10-12 audit).

    Ikkita parallel so'rov bir xil `provider_transaction_id` bilan deyarli bir
    vaqtda kelsa, ikkalasi ham boshlang'ich "mavjud emas" tekshiruvidan
    (TOCTOU) o'tib ketishi mumkin edi. Bu yerda ikkinchi chaqiruvning ichki
    tekshiruvini sun'iy ravishda bir marta "topilmadi" deb simulyatsiya
    qilamiz — birinchi chaqiruv allaqachon yozib qo'ygan bo'lsa ham. To'g'ri
    ishlasa: DB'dagi UNIQUE(provider, provider_transaction_id) cheklovi
    ikkinchi INSERT'ni rad etadi, xizmat buni ushlab birinchi yozuvni
    qaytaradi — yangi dublikat yaratilmaydi.
    """
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = {"id": "payme-tx-race-1", "account": {"ref": ref}, "amount": 50000 * 100}

    service = PaymeService(db_session)
    first = await service.create_transaction(params)

    real_get = service._get_by_provider_id
    call_count = {"n": 0}

    async def fake_get(provider_tx_id: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None  # race'ni simulyatsiya qilish — "hali ko'rinmayapti"
        return await real_get(provider_tx_id)

    monkeypatch.setattr(service, "_get_by_provider_id", fake_get)

    second = await service.create_transaction(params)

    assert second["transaction"] == first["transaction"]
    assert (
        call_count["n"] == 2
    )  # 1-chaqiruv: soxta None, 2-chaqiruv: IntegrityError'dan keyingi recovery


@pytest.mark.asyncio
async def test_create_transaction_rejects_amount_mismatch_for_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.YEARLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    params = {"id": "payme-tx-3", "account": {"ref": ref}, "amount": 1 * 100}

    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).create_transaction(params)

    assert exc_info.value.code == PaymeErrorCode.INVALID_AMOUNT


@pytest.mark.asyncio
async def test_create_transaction_for_subscription_succeeds(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.MONTHLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    price_tiyin = PLAN_PRICES_SOM[SubscriptionPlan.MONTHLY] * 100
    params = {"id": "payme-tx-4", "account": {"ref": ref}, "amount": price_tiyin}

    result = await PaymeService(db_session).create_transaction(params)

    assert result["state"] == PAYME_STATE_CREATED


@pytest.mark.asyncio
async def test_perform_transaction_activates_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-5", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    result = await service.perform_transaction({"id": "payme-tx-5"})

    assert result["state"] == PAYME_STATE_PERFORMED
    await db_session.refresh(commitment)
    assert commitment.status == CommitmentStatus.ACTIVE


@pytest.mark.asyncio
async def test_perform_transaction_activates_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.MONTHLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    price_tiyin = PLAN_PRICES_SOM[SubscriptionPlan.MONTHLY] * 100
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-6", "account": {"ref": ref}, "amount": price_tiyin}
    )

    await service.perform_transaction({"id": "payme-tx-6"})

    await db_session.refresh(subscription)
    assert subscription.is_active is True


@pytest.mark.asyncio
async def test_perform_transaction_is_idempotent_when_already_performed(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-7", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    first = await service.perform_transaction({"id": "payme-tx-7"})
    second = await service.perform_transaction({"id": "payme-tx-7"})

    assert first["perform_time"] == second["perform_time"]
    assert second["state"] == PAYME_STATE_PERFORMED


@pytest.mark.asyncio
async def test_perform_transaction_raises_for_unknown_id(
    db_session: AsyncSession, test_user: User
) -> None:
    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).perform_transaction({"id": "no-such-tx"})

    assert exc_info.value.code == PaymeErrorCode.TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_perform_transaction_rejects_cancelled_transaction(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-8", "account": {"ref": ref}, "amount": 50000 * 100}
    )
    await service.cancel_transaction({"id": "payme-tx-8"})

    with pytest.raises(PaymeRPCError) as exc_info:
        await service.perform_transaction({"id": "payme-tx-8"})

    assert exc_info.value.code == PaymeErrorCode.UNABLE_TO_PERFORM_OPERATION


@pytest.mark.asyncio
async def test_cancel_transaction_before_perform_cancels_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-9", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    result = await service.cancel_transaction({"id": "payme-tx-9"})

    assert result["state"] == PAYME_STATE_CANCELLED_AFTER_CREATE
    await db_session.refresh(commitment)
    assert commitment.status == CommitmentStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_transaction_after_perform_reverses_commitment_deposit(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-10", "account": {"ref": ref}, "amount": 50000 * 100}
    )
    await service.perform_transaction({"id": "payme-tx-10"})

    result = await service.cancel_transaction({"id": "payme-tx-10"})

    assert result["state"] == PAYME_STATE_CANCELLED_AFTER_PERFORM
    await db_session.refresh(commitment)
    assert commitment.status == CommitmentStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_transaction_after_perform_deactivates_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.MONTHLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    price_tiyin = PLAN_PRICES_SOM[SubscriptionPlan.MONTHLY] * 100
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-11", "account": {"ref": ref}, "amount": price_tiyin}
    )
    await service.perform_transaction({"id": "payme-tx-11"})

    await service.cancel_transaction({"id": "payme-tx-11"})

    await db_session.refresh(subscription)
    assert subscription.is_active is False


@pytest.mark.asyncio
async def test_cancel_transaction_is_idempotent(db_session: AsyncSession, test_user: User) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-12", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    first = await service.cancel_transaction({"id": "payme-tx-12"})
    second = await service.cancel_transaction({"id": "payme-tx-12"})

    assert first["cancel_time"] == second["cancel_time"]


@pytest.mark.asyncio
async def test_check_transaction_returns_current_state(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    created = await service.create_transaction(
        {"id": "payme-tx-13", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    result = await service.check_transaction({"id": "payme-tx-13"})

    assert result["transaction"] == created["transaction"]
    assert result["state"] == PAYME_STATE_CREATED


@pytest.mark.asyncio
async def test_check_transaction_raises_for_unknown_id(
    db_session: AsyncSession, test_user: User
) -> None:
    with pytest.raises(PaymeRPCError) as exc_info:
        await PaymeService(db_session).check_transaction({"id": "no-such-tx"})

    assert exc_info.value.code == PaymeErrorCode.TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_get_statement_returns_transactions_within_range(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-14", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    now_millis = int(datetime.now(UTC).timestamp() * 1000)
    result = await service.get_statement({"from": now_millis - 60_000, "to": now_millis + 60_000})

    assert any(t["id"] == "payme-tx-14" for t in result["transactions"])


@pytest.mark.asyncio
async def test_get_statement_excludes_transactions_outside_range(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = PaymeService(db_session)
    await service.create_transaction(
        {"id": "payme-tx-15", "account": {"ref": ref}, "amount": 50000 * 100}
    )

    now_millis = int(datetime.now(UTC).timestamp() * 1000)
    result = await service.get_statement({"from": now_millis - 120_000, "to": now_millis - 60_000})

    assert all(t["id"] != "payme-tx-15" for t in result["transactions"])
