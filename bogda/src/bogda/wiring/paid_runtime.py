"""Env-driven construction of the paid-call service for deployed flows."""

from __future__ import annotations

import os
from pathlib import Path

from bogda.events.jsonl import JsonlRunEventSink
from bogda.model_runtime import PaidModelCallService
from bogda.model_runtime.archive import FilePromptArchive
from bogda.model_runtime.dsh import DshCliAdapter
from bogda.model_runtime.routing import ModelRouter
from bogda.wiring.store_api import (
    RemoteBudgetService,
    RemoteUsageUnknownRecovery,
    StoreApiClient,
)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for paid model calls")
    return value


def _hmac_key() -> bytes:
    raw = _required_env("BOGDA_APPROVAL_HMAC_KEY")
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise RuntimeError("BOGDA_APPROVAL_HMAC_KEY must be hex") from None
    if len(key) < 32:
        raise RuntimeError("BOGDA_APPROVAL_HMAC_KEY must be at least 32 bytes")
    return key


def _default_patch_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "dsh-patches"


def build_paid_service_from_env(*, run_id: str) -> PaidModelCallService:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    base_url = _required_env("BOGDA_STORE_API_URL")
    artifact_root = Path(_required_env("BOGDA_ARTIFACT_ROOT"))
    patch_dir = Path(os.environ.get("BOGDA_DSH_PATCH_DIR") or _default_patch_dir())

    client = StoreApiClient(base_url, _hmac_key())
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return PaidModelCallService(
        router=ModelRouter(),
        archive=FilePromptArchive(artifact_root),
        budget=RemoteBudgetService(client),
        event_sink=JsonlRunEventSink(run_dir / "events.jsonl"),
        executor=DshCliAdapter(
            patch_dir / "flash.yml",
            patch_dir / "pro.yml",
        ),
        recovery=RemoteUsageUnknownRecovery(client),
    )


__all__ = ["build_paid_service_from_env"]
