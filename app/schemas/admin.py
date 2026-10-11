"""
Ichki monitoring (admin.py) uchun sxemalar.
"""

from pydantic import BaseModel


class AdminDashboardSchema(BaseModel):
    total_users: int
    active_users: int
    users_by_tier: dict[str, int]
    total_organizations: int
    total_completed_sessions: int
    total_focus_minutes: int
