from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class RedemptionCreateRequest(BaseModel):
    points: StrictInt = Field(ge=100, le=1_000_000_000)


class RedemptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    points: int
    raw_chicken_grams: int
    status: str
    expires_at: datetime
    fulfilled_grams: int | None
    fulfilled_at: datetime | None
    created_at: datetime


class RedemptionCreatedResponse(RedemptionResponse):
    qr_svg: str


class RedemptionQrResponse(BaseModel):
    redemption_id: UUID
    expires_at: datetime
    qr_svg: str


class RedemptionCancelResponse(RedemptionResponse):
    refunded_points: int


class StaffRedemptionVerifyRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class StaffRedemptionVerifyResponse(BaseModel):
    redemption_id: UUID
    customer_name: str
    points_reserved: int
    maximum_grams: int
    status: str
    expires_at: datetime


class StaffRedemptionFulfillRequest(StaffRedemptionVerifyRequest):
    grams: StrictInt = Field(ge=1, le=1_000_000_000)


class StaffRedemptionFulfillResponse(BaseModel):
    redemption_id: UUID
    status: str
    fulfilled_grams: int
    refunded_points: int
    fulfilled_at: datetime
