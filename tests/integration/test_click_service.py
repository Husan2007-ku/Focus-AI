"""ClickService uchun testlar — Prepare/Complete protokoli, imzo tekshiruvi,
moliyaviy maqsad (commitment) va obuna (subscription) to'lov oqimlari.

Click protokolida tashqi HTTP chaqiruvi yo'q (checkout URL — oddiy string
formatlash, imzo — mahalliy MD5 hisob-kitob), shuning uchun bu yerda mock
kerak emas — hammasi haqiqiy DB (`db_session`) bilan ishlaydi.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.click_client import ClickAction, ClickErrorCode
from app.models.finance import CommitmentStatus, FinancialCommitment
from app.models.subscription import PLAN_PRICES_SOM, Subscription, SubscriptionPlan
from app.models.user import User
from app.services.click_service import ClickService
from app.utils.payment_ref import PaymentTargetKind, build_payment_ref


def _sign(
    *,
    click_trans_id: str,
    merchant_trans_id: str,
    amount: str,
    action: int,
    sign_time: str,
    merchant_prepare_id: str | None = None,
) -> str:
    """Click'ning haqiqiy `verify_signature()` formulasi bilan bir xil tartibda
    imzo hisoblaydi — testlarda ishlatiladigan sozlamalar (CLICK_SECRET_KEY va
    h.k.) qanday bo'lishidan qat'iy nazar, ikkalasi doim mos keladi."""
    if merchant_prepare_id is not None:
        raw = (
            f"{click_trans_id}{settings.CLICK_SERVICE_ID}{settings.CLICK_SECRET_KEY}"
            f"{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
        )
    else:
        raw = (
            f"{click_trans_id}{settings.CLICK_SERVICE_ID}{settings.CLICK_SECRET_KEY}"
            f"{merchant_trans_id}{amount}{action}{sign_time}"
        )
    return hashlib.md5(raw.encode()).hexdigest()


def _prepare_params(
    *, click_trans_id: str, merchant_trans_id: str, amount: str
) -> dict[str, object]:
    sign_time = "2026-10-12 00:00:00"
    return {
        "click_trans_id": click_trans_id,
        "service_id": settings.CLICK_SERVICE_ID,
        "merchant_trans_id": merchant_trans_id,
        "amount": amount,
        "action": ClickAction.PREPARE,
        "sign_time": sign_time,
        "sign_string": _sign(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            action=ClickAction.PREPARE,
            sign_time=sign_time,
        ),
    }


def _complete_params(
    *,
    click_trans_id: str,
    merchant_trans_id: str,
    amount: str,
    merchant_prepare_id: str,
    click_error: int = 0,
) -> dict[str, object]:
    sign_time = "2026-10-12 00:05:00"
    return {
        "click_trans_id": click_trans_id,
        "service_id": settings.CLICK_SERVICE_ID,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": merchant_prepare_id,
        "amount": amount,
        "action": ClickAction.COMPLETE,
        "sign_time": sign_time,
        "error": click_error,
        "sign_string": _sign(
            click_trans_id=click_trans_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            action=ClickAction.COMPLETE,
            sign_time=sign_time,
            merchant_prepare_id=merchant_prepare_id,
        ),
    }


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
async def test_prepare_creates_transaction_for_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user)
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1001", merchant_trans_id=ref, amount="50000")

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.SUCCESS
    assert "merchant_prepare_id" in result


@pytest.mark.asyncio
async def test_prepare_rejects_invalid_signature(db_session: AsyncSession, test_user: User) -> None:
    commitment = await _make_commitment(db_session, test_user)
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1002", merchant_trans_id=ref, amount="50000")
    params["sign_string"] = "notoliq-imzo"

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.SIGN_CHECK_FAILED


@pytest.mark.asyncio
async def test_prepare_is_idempotent_for_same_click_trans_id(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user)
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1003", merchant_trans_id=ref, amount="50000")

    service = ClickService(db_session)
    first = await service.prepare(params)
    second = await service.prepare(params)

    assert first["merchant_prepare_id"] == second["merchant_prepare_id"]


@pytest.mark.asyncio
async def test_prepare_handles_concurrent_duplicate_via_db_constraint(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Race-condition regressiya testi (2026-10-12 audit) — payme_service.py'dagi
    bir xil naqsh, Click uchun. Qarang: test_payme_service.py'dagi tarjimasi."""
    commitment = await _make_commitment(db_session, test_user)
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1099", merchant_trans_id=ref, amount="50000")

    service = ClickService(db_session)
    first = await service.prepare(params)

    real_get = service._get_by_click_id
    call_count = {"n": 0}

    async def fake_get(click_trans_id: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        return await real_get(click_trans_id)

    monkeypatch.setattr(service, "_get_by_click_id", fake_get)

    second = await service.prepare(params)

    assert second["merchant_prepare_id"] == first["merchant_prepare_id"]
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_prepare_rejects_malformed_reference(
    db_session: AsyncSession, test_user: User
) -> None:
    params = _prepare_params(
        click_trans_id="1004", merchant_trans_id="not-a-valid-ref", amount="50000"
    )

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.USER_NOT_FOUND


@pytest.mark.asyncio
async def test_prepare_rejects_unknown_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, uuid.uuid4())
    params = _prepare_params(click_trans_id="1005", merchant_trans_id=ref, amount="50000")

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.USER_NOT_FOUND


@pytest.mark.asyncio
async def test_prepare_rejects_already_paid_commitment(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user)
    commitment.status = CommitmentStatus.ACTIVE
    await db_session.commit()
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1006", merchant_trans_id=ref, amount="50000")

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.ALREADY_PAID


@pytest.mark.asyncio
async def test_prepare_rejects_amount_mismatch(db_session: AsyncSession, test_user: User) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    params = _prepare_params(click_trans_id="1007", merchant_trans_id=ref, amount="1")

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.INVALID_AMOUNT


@pytest.mark.asyncio
async def test_prepare_creates_transaction_for_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.MONTHLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    price = str(PLAN_PRICES_SOM[SubscriptionPlan.MONTHLY])
    params = _prepare_params(click_trans_id="1008", merchant_trans_id=ref, amount=price)

    result = await ClickService(db_session).prepare(params)

    assert result["error"] == ClickErrorCode.SUCCESS


@pytest.mark.asyncio
async def test_complete_activates_commitment_and_writes_ledger(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = ClickService(db_session)

    prepared = await service.prepare(
        _prepare_params(click_trans_id="1009", merchant_trans_id=ref, amount="50000")
    )
    result = await service.complete(
        _complete_params(
            click_trans_id="1009",
            merchant_trans_id=ref,
            amount="50000",
            merchant_prepare_id=prepared["merchant_prepare_id"],
        )
    )

    assert result["error"] == ClickErrorCode.SUCCESS
    await db_session.refresh(commitment)
    assert commitment.status == CommitmentStatus.ACTIVE


@pytest.mark.asyncio
async def test_complete_activates_subscription(db_session: AsyncSession, test_user: User) -> None:
    subscription = await _make_subscription(db_session, test_user, SubscriptionPlan.YEARLY)
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
    price = str(PLAN_PRICES_SOM[SubscriptionPlan.YEARLY])
    service = ClickService(db_session)

    prepared = await service.prepare(
        _prepare_params(click_trans_id="1010", merchant_trans_id=ref, amount=price)
    )
    await service.complete(
        _complete_params(
            click_trans_id="1010",
            merchant_trans_id=ref,
            amount=price,
            merchant_prepare_id=prepared["merchant_prepare_id"],
        )
    )

    await db_session.refresh(subscription)
    assert subscription.is_active is True


@pytest.mark.asyncio
async def test_complete_is_idempotent_when_already_performed(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = ClickService(db_session)
    prepared = await service.prepare(
        _prepare_params(click_trans_id="1011", merchant_trans_id=ref, amount="50000")
    )
    complete_params = _complete_params(
        click_trans_id="1011",
        merchant_trans_id=ref,
        amount="50000",
        merchant_prepare_id=prepared["merchant_prepare_id"],
    )

    first = await service.complete(complete_params)
    second = await service.complete(complete_params)

    assert first["merchant_confirm_id"] == second["merchant_confirm_id"]
    assert second["error"] == ClickErrorCode.SUCCESS


@pytest.mark.asyncio
async def test_complete_cancels_transaction_on_negative_click_error(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = ClickService(db_session)
    prepared = await service.prepare(
        _prepare_params(click_trans_id="1012", merchant_trans_id=ref, amount="50000")
    )

    result = await service.complete(
        _complete_params(
            click_trans_id="1012",
            merchant_trans_id=ref,
            amount="50000",
            merchant_prepare_id=prepared["merchant_prepare_id"],
            click_error=-1,
        )
    )

    assert result["error"] == ClickErrorCode.TRANSACTION_CANCELLED
    await db_session.refresh(commitment)
    assert commitment.status == CommitmentStatus.CANCELLED


@pytest.mark.asyncio
async def test_complete_rejects_invalid_signature(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = ClickService(db_session)
    prepared = await service.prepare(
        _prepare_params(click_trans_id="1013", merchant_trans_id=ref, amount="50000")
    )
    params = _complete_params(
        click_trans_id="1013",
        merchant_trans_id=ref,
        amount="50000",
        merchant_prepare_id=prepared["merchant_prepare_id"],
    )
    params["sign_string"] = "notoliq-imzo"

    result = await service.complete(params)

    assert result["error"] == ClickErrorCode.SIGN_CHECK_FAILED


@pytest.mark.asyncio
async def test_complete_returns_not_found_for_unknown_transaction(
    db_session: AsyncSession, test_user: User
) -> None:
    params = _complete_params(
        click_trans_id="no-such-transaction",
        merchant_trans_id="commitment:" + str(uuid.uuid4()),
        amount="50000",
        merchant_prepare_id=str(uuid.uuid4()),
    )

    result = await ClickService(db_session).complete(params)

    assert result["error"] == ClickErrorCode.TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_complete_returns_cancelled_for_already_cancelled_transaction(
    db_session: AsyncSession, test_user: User
) -> None:
    commitment = await _make_commitment(db_session, test_user, amount="50000")
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
    service = ClickService(db_session)
    prepared = await service.prepare(
        _prepare_params(click_trans_id="1014", merchant_trans_id=ref, amount="50000")
    )
    await service.complete(
        _complete_params(
            click_trans_id="1014",
            merchant_trans_id=ref,
            amount="50000",
            merchant_prepare_id=prepared["merchant_prepare_id"],
            click_error=-1,
        )
    )

    result = await service.complete(
        _complete_params(
            click_trans_id="1014",
            merchant_trans_id=ref,
            amount="50000",
            merchant_prepare_id=prepared["merchant_prepare_id"],
        )
    )

    assert result["error"] == ClickErrorCode.TRANSACTION_CANCELLED
