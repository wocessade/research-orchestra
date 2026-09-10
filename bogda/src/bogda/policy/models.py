from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bogda.contracts import AutonomyMode, ModelTier


class ModelPolicyValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_model_tier: ModelTier = ModelTier.AUTO
    allow_auto_upgrade: bool = True
    allow_flash_downgrade: bool = True
    prefer_off_peak: bool = True
    auto_resume: bool = True
    minimum_remaining: Decimal = Field(default=Decimal("10.00"), ge=0)
    critical_notifications: bool = True
    workload_safety_margin: Decimal = Field(default=Decimal("1.20"), ge=1)

    @field_validator("minimum_remaining", "workload_safety_margin", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_default: ModelPolicyValues = Field(default_factory=ModelPolicyValues)
    project_overrides: dict[str, ModelPolicyValues] = Field(default_factory=dict)
    revision: int = Field(default=0, ge=0)


class ResolvedModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None
    values: ModelPolicyValues
    source: Literal["global", "project"]
    inherits_global: bool
    policy_revision: int


class AutonomyPolicy(BaseModel):
    global_default: AutonomyMode = AutonomyMode.SUPERVISED
    project_overrides: dict[str, AutonomyMode] = Field(default_factory=dict)
    revision: int = Field(default=0, ge=0)


class ResolvedAutonomyMode(BaseModel):
    project_id: str
    effective_mode: AutonomyMode
    mode_source: Literal["global-default", "project-override"]
    policy_revision: int
