from typing import Literal

from pydantic import BaseModel, Field

from bogda.contracts import AutonomyMode


class AutonomyPolicy(BaseModel):
    global_default: AutonomyMode = AutonomyMode.SUPERVISED
    project_overrides: dict[str, AutonomyMode] = Field(default_factory=dict)
    revision: int = Field(default=0, ge=0)


class ResolvedAutonomyMode(BaseModel):
    project_id: str
    effective_mode: AutonomyMode
    mode_source: Literal["global-default", "project-override"]
    policy_revision: int
