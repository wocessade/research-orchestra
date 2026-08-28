from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator


class TaskIntent(StrEnum):
    EXECUTE = "execute"
    EXPLORE = "explore"
    DECIDE = "decide"
    AUDIT = "audit"
    BRIEF = "brief"


class ModelTier(StrEnum):
    AUTO = "auto"
    FLASH = "flash"
    PRO = "pro"


class ExecutorKind(StrEnum):
    DSH = "dsh"
    SHELL = "shell"


class PricePreference(StrEnum):
    IMMEDIATE = "immediate"
    CHEAPEST_BEFORE_DEADLINE = "cheapest_before_deadline"


class SchedulePolicy(BaseModel):
    earliest_start: datetime | None = None
    deadline: datetime | None = None
    price_preference: PricePreference = PricePreference.CHEAPEST_BEFORE_DEADLINE

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        for name in ("earliest_start", "deadline"):
            value = getattr(self, name)
            if value is not None and value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if (
            self.earliest_start is not None
            and self.deadline is not None
            and self.deadline <= self.earliest_start
        ):
            raise ValueError("deadline must be after earliest_start")
        return self
