from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WalletSummaryResponse(BaseModel):
    balance_points: int
    raw_chicken_grams: int
    minimum_redemption_points: int
    points_to_grams_rule: str = "1 point = 1 gram of raw chicken"


class WalletTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_type: str
    points_delta: int
    description: str
    created_at: datetime
