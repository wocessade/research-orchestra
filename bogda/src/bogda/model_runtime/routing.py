from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from bogda.contracts import JobRequest, ModelTier, TaskIntent


LOW_RISK_FALLBACK_INTENTS = frozenset(
    {TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE}
)


class RouteDecisionKind(StrEnum):
    SELECTED = "selected"
    DOWNGRADED = "downgraded"
    PRO_REQUIRED = "pro_required"


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: RouteDecisionKind
    requested_tier: ModelTier
    effective_tier: ModelTier | None

    @model_validator(mode="after")
    def validate_effective_tier(self) -> RouteDecision:
        if self.kind is RouteDecisionKind.PRO_REQUIRED:
            if self.effective_tier is not None:
                raise ValueError("pro_required decisions cannot select a tier")
        elif self.effective_tier in (None, ModelTier.AUTO):
            raise ValueError("selected decisions require a concrete effective tier")
        return self


class ModelRouter:
    def select(
        self,
        request: JobRequest,
        *,
        pro_available: bool,
        allow_low_risk_fallback: bool,
    ) -> RouteDecision:
        envelope = request.budget
        if envelope is None:
            raise ValueError("paid model routing requires a budget envelope")

        requested = envelope.requested_tier
        if requested is ModelTier.AUTO:
            raise ValueError("budget requested_tier must be a concrete tier")

        if (
            request.model_tier is ModelTier.AUTO
            and request.intent in {TaskIntent.DECIDE, TaskIntent.AUDIT}
            and requested is ModelTier.FLASH
        ):
            raise ValueError("AUTO high-risk requests cannot use a frozen Flash envelope")

        if requested is ModelTier.FLASH:
            return RouteDecision(
                kind=RouteDecisionKind.SELECTED,
                requested_tier=requested,
                effective_tier=ModelTier.FLASH,
            )

        if pro_available:
            return RouteDecision(
                kind=RouteDecisionKind.SELECTED,
                requested_tier=requested,
                effective_tier=ModelTier.PRO,
            )

        if (
            request.intent in LOW_RISK_FALLBACK_INTENTS
            and envelope.fallback_tier is ModelTier.FLASH
            and allow_low_risk_fallback
        ):
            return RouteDecision(
                kind=RouteDecisionKind.DOWNGRADED,
                requested_tier=requested,
                effective_tier=ModelTier.FLASH,
            )

        return RouteDecision(
            kind=RouteDecisionKind.PRO_REQUIRED,
            requested_tier=requested,
            effective_tier=None,
        )


__all__ = [
    "LOW_RISK_FALLBACK_INTENTS",
    "ModelRouter",
    "RouteDecision",
    "RouteDecisionKind",
]
