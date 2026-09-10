"""Machine-facing store endpoints for the runner, authenticated by HMAC.

The console owns the durable budget/approval/usage stores on this host; the
runner reaches them only through these endpoints and never opens the SQLite
files directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from bogda_console.config import Settings


router = APIRouter(prefix="/api/v1/store")


def _container(request: Request) -> Any:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(status_code=503, detail="store backend is not available")
    return container


def _verify(settings: Settings, request: Request, body: bytes) -> None:
    key = settings.approval_hmac_key
    if not key:
        raise HTTPException(status_code=503, detail="store api is not enabled")
    try:
        from bogda.wiring.store_api import StoreApiError, verify_request
    except ImportError:
        raise HTTPException(
            status_code=503, detail="store api backend is not available"
        ) from None
    raw_timestamp = request.headers.get("X-Bogda-Timestamp", "")
    signature = request.headers.get("X-Bogda-Signature", "")
    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401, detail="store api authentication failed"
        ) from None
    try:
        verify_request(
            key,
            request.method,
            request.url.path,
            body,
            timestamp,
            signature,
            now_epoch=int(datetime.now(timezone.utc).timestamp()),
        )
    except StoreApiError:
        raise HTTPException(
            status_code=401, detail="store api authentication failed"
        ) from None


async def require_store_auth(request: Request) -> None:
    body = await request.body()
    container = _container(request)
    _verify(container.settings, request, body)


def _stores(request: Request) -> Any:
    container = _container(request)
    stores = getattr(container, "stores", None)
    if stores is None:
        raise HTTPException(status_code=503, detail="store backend is not wired")
    return stores


class BudgetAdmitRequest(BaseModel):
    run_id: str
    intent: str
    envelope: dict[str, Any]
    reservation_cny: str | None = None


class BudgetReleaseRequest(BaseModel):
    reservation_id: str
    intent: str
    requested_tier: str
    pricing_version: str


class BudgetReconcileRequest(BudgetReleaseRequest):
    actual_cost_cny: str


class UsageUnknownCaseRequest(BaseModel):
    run_id: str
    call_id: str
    reservation_id: str
    intent: str
    requested_tier: str
    effective_tier: str | None = None
    pricing_version: str
    prompt_hash: str | None = None
    prompt_artifact: str | None = None
    case_id: str | None = None


@router.post("/budget/admit", dependencies=[Depends(require_store_auth)])
async def budget_admit(payload: BudgetAdmitRequest, request: Request):
    from bogda.contracts import RunBudgetEnvelope, TaskIntent
    from bogda.wiring.store_api import admission_to_wire

    stores = _stores(request)
    try:
        envelope = RunBudgetEnvelope.model_validate(payload.envelope)
        intent = TaskIntent(payload.intent)
        reservation = (
            None if payload.reservation_cny is None else Decimal(payload.reservation_cny)
        )
    except Exception:
        raise HTTPException(status_code=422, detail="store request is invalid") from None
    credential = None
    if stores.approvals is not None:
        try:
            credential = stores.approvals.get_open(payload.run_id)
        except Exception:
            credential = None
    try:
        await stores.balance_usage.refresh()
    except Exception:
        pass
    try:
        result = stores.budget.admit(
            payload.run_id, intent, envelope, reservation, approval=credential
        )
    except Exception:
        raise HTTPException(status_code=503, detail="budget admission failed") from None
    return {"result": admission_to_wire(result)}


@router.post("/budget/release", dependencies=[Depends(require_store_auth)])
async def budget_release(payload: BudgetReleaseRequest, request: Request):
    from bogda.contracts import ModelTier, TaskIntent
    from bogda.wiring.store_api import reservation_to_wire

    stores = _stores(request)
    try:
        intent = TaskIntent(payload.intent)
        tier = ModelTier(payload.requested_tier)
    except Exception:
        raise HTTPException(status_code=422, detail="store request is invalid") from None
    try:
        reservation = stores.budget.release(
            payload.reservation_id,
            intent=intent,
            requested_tier=tier,
            pricing_version=payload.pricing_version,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=409, detail="budget release failed") from None
    return {"reservation": reservation_to_wire(reservation)}


@router.post("/budget/reconcile", dependencies=[Depends(require_store_auth)])
async def budget_reconcile(payload: BudgetReconcileRequest, request: Request):
    from bogda.contracts import ModelTier, TaskIntent
    from bogda.wiring.store_api import reservation_to_wire

    stores = _stores(request)
    try:
        intent = TaskIntent(payload.intent)
        tier = ModelTier(payload.requested_tier)
        actual_cost = Decimal(payload.actual_cost_cny)
    except Exception:
        raise HTTPException(status_code=422, detail="store request is invalid") from None
    try:
        reservation = stores.budget.reconcile(
            payload.reservation_id,
            actual_cost,
            intent=intent,
            requested_tier=tier,
            pricing_version=payload.pricing_version,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=409, detail="budget reconciliation failed") from None
    return {"reservation": reservation_to_wire(reservation)}


@router.get("/usage-unknown/blocked", dependencies=[Depends(require_store_auth)])
async def usage_unknown_blocked(
    request: Request,
    run_id: str = Query(...),
    call_id: str = Query(...),
):
    stores = _stores(request)
    try:
        blocked = stores.recovery.blocks_original_call(run_id, call_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503, detail="usage-unknown lookup failed"
        ) from None
    return {"blocked": bool(blocked)}


@router.post("/usage-unknown/cases", dependencies=[Depends(require_store_auth)])
async def usage_unknown_open_case(payload: UsageUnknownCaseRequest, request: Request):
    from bogda.contracts import ModelTier, TaskIntent
    from bogda.model_runtime.recovery import UsageUnknownConflictError
    from bogda.wiring.store_api import case_to_wire

    stores = _stores(request)
    try:
        intent = TaskIntent(payload.intent)
        requested_tier = ModelTier(payload.requested_tier)
        effective_tier = (
            None if payload.effective_tier is None else ModelTier(payload.effective_tier)
        )
    except Exception:
        raise HTTPException(status_code=422, detail="store request is invalid") from None
    try:
        case = stores.recovery.open_case(
            run_id=payload.run_id,
            call_id=payload.call_id,
            reservation_id=payload.reservation_id,
            intent=intent,
            requested_tier=requested_tier,
            effective_tier=effective_tier,
            pricing_version=payload.pricing_version,
            prompt_hash=payload.prompt_hash,
            prompt_artifact=payload.prompt_artifact,
            case_id=payload.case_id,
        )
    except UsageUnknownConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="usage-unknown case failed") from None
    return {"case": case_to_wire(case)}
