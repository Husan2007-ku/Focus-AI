"""
`app.utils.payment_ref` uchun testlar — bu Payme/Click to'lovlarini to'g'ri
turga (commitment/subscription) yo'naltirishning yagona manbai, shuning
uchun to'g'riligi juda muhim.
"""

import uuid

import pytest

from app.utils.payment_ref import PaymentTargetKind, build_payment_ref, parse_payment_ref


def test_build_and_parse_commitment_ref() -> None:
    target_id = uuid.uuid4()
    ref = build_payment_ref(PaymentTargetKind.COMMITMENT, target_id)

    kind, parsed_id = parse_payment_ref(ref)

    assert kind == PaymentTargetKind.COMMITMENT
    assert parsed_id == target_id


def test_build_and_parse_subscription_ref() -> None:
    target_id = uuid.uuid4()
    ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, target_id)

    kind, parsed_id = parse_payment_ref(ref)

    assert kind == PaymentTargetKind.SUBSCRIPTION
    assert parsed_id == target_id


@pytest.mark.parametrize(
    "invalid_ref",
    [
        "",
        "no-colon-here",
        "commitment:",
        ":missing-kind",
        "unknown_kind:12345678-1234-1234-1234-123456789012",
        "commitment:not-a-valid-uuid",
    ],
)
def test_parse_invalid_ref_raises(invalid_ref: str) -> None:
    with pytest.raises(ValueError):
        parse_payment_ref(invalid_ref)
