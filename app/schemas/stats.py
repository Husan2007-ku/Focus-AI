"""
Shaxsiy statistika va haftalik AI xulosa (stats.py) uchun sxemalar.
"""

from datetime import date

from pydantic import BaseModel


class StatsSummarySchema(BaseModel):
    total_completed_sessions: int
    total_focus_minutes: int
    weekly_completed_sessions: int
    weekly_focus_minutes: int
    current_streak: int
    longest_streak: int
    total_xp: int


class WeeklyAISummarySchema(BaseModel):
    week_start: date
    week_end: date
    weekly_completed_sessions: int
    weekly_focus_minutes: int
    summary: str
