"""add unique constraint on transactions provider+provider_transaction_id

Revision ID: 541886fde790
Revises: d832eba0d61e
Create Date: 2026-10-12 00:00:00.000000

MUHIM (xavfsizlik auditi, 2026-10-12): Payme/Click webhook'lari tarmoq
muammosi tufayli bir xil tranzaksiyani concurrent (bir vaqtda, ikki
parallel HTTP so'rov sifatida) qayta yuborishi mumkin. Avval
`transactions.provider_transaction_id` ustida faqat oddiy (unique bo'lmagan)
index bor edi — xizmat qatlami "mavjudligini SELECT bilan tekshir, keyin
INSERT qil" degan mantiqda ishlagani uchun, ikkita parallel so'rov bir xil
tranzaksiyani ikki marta yaratishi (race condition) mumkin edi. Bu
migratsiya DB darajasida `UNIQUE(provider, provider_transaction_id)`
cheklovini qo'shadi — endi faqat bittasi muvaffaqiyatli INSERT qila oladi,
ikkinchisi `IntegrityError` oladi (xizmat qatlamida ushlanadi, qarang:
app/services/payme_service.py va app/services/click_service.py).

ESLATMA: agar bu migratsiya "duplicate key" xatosi bilan muvaffaqiyatsiz
tugasa — demak bazada allaqachon shu cheklovni buzadigan takroriy
qatorlar bor. Bu holda migratsiyani qo'llashdan oldin ularni qo'lda
tekshirib chiqish kerak (avtomatik o'chirish yoki birlashtirish xavfli —
moliyaviy ma'lumot, shuning uchun bu yerda avtomatlashtirilmagan).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "541886fde790"
down_revision: str | None = "d832eba0d61e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_transactions_provider_provider_tx_id",
        "transactions",
        ["provider", "provider_transaction_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_transactions_provider_provider_tx_id", "transactions", type_="unique")
