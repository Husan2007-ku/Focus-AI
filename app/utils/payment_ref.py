"""
To'lov "reference" kodlash/dekodlash — Payme va Click uchun bir xil mexanizm.

Muammo: Click faqat bitta `merchant_trans_id` (oddiy matn) yuboradi, unda
"bu commitment to'lovimi yoki obuna to'lovimi" degan ma'lumot yo'q. Buni hal
qilish uchun ID oldiga turi qo'shiladi: "commitment:<uuid>" yoki
"subscription:<uuid>". Payme'da ham bir xillik uchun aynan shu format
ishlatiladi (`ac.ref=<reference>`).
"""

import uuid
from enum import StrEnum


class PaymentTargetKind(StrEnum):
    COMMITMENT = "commitment"
    SUBSCRIPTION = "subscription"


def build_payment_ref(kind: PaymentTargetKind, target_id: uuid.UUID) -> str:
    return f"{kind.value}:{target_id}"


def parse_payment_ref(ref: str) -> tuple[PaymentTargetKind, uuid.UUID]:
    kind_str, _, id_str = ref.partition(":")
    if not kind_str or not id_str:
        raise ValueError(f"Yaroqsiz to'lov reference formati: {ref!r}")

    try:
        kind = PaymentTargetKind(kind_str)
    except ValueError as exc:
        raise ValueError(f"Noma'lum to'lov turi: {kind_str!r}") from exc

    try:
        target_id = uuid.UUID(id_str)
    except ValueError as exc:
        raise ValueError(f"Yaroqsiz UUID: {id_str!r}") from exc

    return kind, target_id
