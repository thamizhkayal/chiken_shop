from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_date: date
    total_customers: int
    daily_active_customers: int
    total_points_issued: int
    outstanding_points: int
    total_points_redeemed: int
    total_chicken_grams_redeemed: int
    pending_redemptions: int
    completed_redemptions: int
    expired_redemptions: int
    cancelled_redemptions: int


class StaffRedemptionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    redemption_id: UUID
    customer_name: str
    points_reserved: int
    status: str
    fulfilled_grams: int | None
    created_at: datetime
    fulfilled_at: datetime | None


class StaffDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_date: date
    pending_redemptions: int
    fulfilled_today: int
    chicken_grams_fulfilled_today: int
    recent_redemptions: list[StaffRedemptionHistoryItem]
