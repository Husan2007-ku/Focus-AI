"""
Barcha SQLAlchemy modellari shu yerda import qilinadi.

Muhim: Alembic autogenerate ishlashi uchun har bir yangi model shu faylga
qo'shilishi SHART, aks holda `alembic revision --autogenerate` uni ko'rmaydi.
"""

from app.models.ai_chat import AIConversation, AIMessage, MessageRole
from app.models.device import Device, DevicePlatform
from app.models.finance import (
    CommitmentStatus,
    FinancialCommitment,
    LedgerEntry,
    LedgerEntryType,
    PaymentProvider,
    Transaction,
    TransactionPurpose,
    TransactionState,
)
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.gamification import BadgeCode, UserBadge, UserStreak, XPReason, XPTransaction
from app.models.organization import Organization, OrganizationStatus
from app.models.routine import DailyRoutine, RoutineStatus
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import AuthProvider, SubscriptionTier, User

__all__ = [
    "User",
    "AuthProvider",
    "SubscriptionTier",
    "FocusSession",
    "FocusSessionStatus",
    "AIConversation",
    "AIMessage",
    "MessageRole",
    "DailyRoutine",
    "RoutineStatus",
    "UserStreak",
    "XPTransaction",
    "XPReason",
    "UserBadge",
    "BadgeCode",
    "Device",
    "DevicePlatform",
    "FinancialCommitment",
    "CommitmentStatus",
    "Transaction",
    "TransactionState",
    "TransactionPurpose",
    "PaymentProvider",
    "LedgerEntry",
    "LedgerEntryType",
    "Subscription",
    "SubscriptionPlan",
    "Organization",
    "OrganizationStatus",
]
