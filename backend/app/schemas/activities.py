from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SpinRewardResponse(BaseModel):
    spun_today: bool
    spins_used: int
    spin_limit: int
    spins_remaining: int
    points_awarded: int
    reward_points: int
    reward_index: int
    business_date: date
    daily_points_earned: int
    daily_points_remaining: int


class SpinStatusResponse(BaseModel):
    enabled: bool
    spun_today: bool
    spins_used: int
    spin_limit: int
    spins_remaining: int
    daily_points_earned: int
    daily_points_remaining: int
    rewards: list["SpinRewardOptionResponse"]


class SpinRewardOptionResponse(BaseModel):
    points: int
    probability_basis_points: int


class PuzzleResponse(BaseModel):
    id: UUID
    prompt: str
    reward_points: int
    business_date: date
    attempted: bool
    is_active: bool


class PuzzleAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=200)


class PuzzleAttemptResponse(BaseModel):
    is_correct: bool
    points_awarded: int
    daily_points_earned: int
    daily_points_remaining: int


class RewardOptionInput(BaseModel):
    points: int = Field(ge=0, le=20)
    probability_basis_points: int = Field(gt=0, le=10_000)


class ActivityConfigurationUpdate(BaseModel):
    enabled: bool
    puzzle_enabled: bool
    daily_activity_cap: int = Field(ge=1, le=10_000)
    rewards: list[RewardOptionInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_reward_probabilities(self) -> "ActivityConfigurationUpdate":
        if sum(item.probability_basis_points for item in self.rewards) != 10_000:
            raise ValueError("Spin reward probabilities must total 10000 basis points")
        if len({item.points for item in self.rewards}) != len(self.rewards):
            raise ValueError("Spin reward point values must be unique")
        return self


class ActivityConfigurationResponse(BaseModel):
    enabled: bool
    puzzle_enabled: bool
    daily_activity_cap: int
    rewards: list[SpinRewardOptionResponse]
    updated_at: datetime


class PuzzleCreateRequest(BaseModel):
    business_date: date
    prompt: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=200)
    reward_points: int = Field(gt=0, le=10_000)
    is_active: bool = True
