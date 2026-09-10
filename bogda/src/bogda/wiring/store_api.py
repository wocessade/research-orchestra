"""HMAC-authenticated narrow store API shared by console (server) and runner (client).

The console owns the durable stores on one host; the runner never opens the
SQLite files directly and reaches them only through these endpoints.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from bogda.budget.guard import BudgetDecision, BudgetDecisionKind
from bogda.budget.ledger import Reservation, ReservationState
from bogda.budget.pricing import catalog_registry
from bogda.budget.service import BudgetAdmissionResult
from bogda.contracts import ModelTier, TaskIntent
from bogda.model_runtime.recovery import UsageUnknownCase, UsageUnknownState

API_DOMAIN = "bogda-store-api"
REPLAY_WINDOW_SECONDS = 300
STORE_PREFIX = "/api/v1/store"


class StoreApiError(RuntimeError):
    """The store API call failed safely (transport, auth, or payload error)."""


def canonical_body(payload: Mapping[str, Any] | None) -> bytes:
    if payload is None:
        return b""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_request(
    key: bytes, method: str, path: str, body: bytes, timestamp: int
) -> str:
    message = "\n".join(
        (
            API_DOMAIN,
            str(timestamp),
            method.upper(),
            path,
            hashlib.sha256(body).hexdigest(),
        )
    )
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_request(
    key: bytes,
    method: str,
    path: str,
    body: bytes,
    timestamp: int,
    signature: str,
    *,
    now_epoch: int,
    window_seconds: int = REPLAY_WINDOW_SECONDS,
) -> None:
    if not isinstance(timestamp, int):
        raise StoreApiError("timestamp is invalid")
    if abs(now_epoch - timestamp) > window_seconds:
        raise StoreApiError("timestamp outside replay window")
    if not isinstance(signature, str) or not signature:
        raise StoreApiError("signature is missing")
    expected = sign_request(key, method, path, body, timestamp)
    if not hmac.compare_digest(expected, signature):
        raise StoreApiError("signature mismatch")


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        raise StoreApiError("decimal field is invalid") from None


def _dt(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise StoreApiError("timestamp field is invalid") from None
    if parsed.utcoffset() is None:
        raise StoreApiError("timestamp field must be timezone-aware")
    return parsed


def decision_to_wire(decision: BudgetDecision) -> dict[str, Any]:
    return {
        "allowed": bool(decision.allowed),
        "kind": decision.kind.value,
        "reason": decision.reason,
        "balance": None if decision.balance is None else format(decision.balance, "f"),
        "active_reservations": format(decision.active_reservations, "f"),
        "minimum_remaining": None
        if decision.minimum_remaining is None
        else format(decision.minimum_remaining, "f"),
        "available_to_start": None
        if decision.available_to_start is None
        else format(decision.available_to_start, "f"),
        "requested_reservation": None
        if decision.requested_reservation is None
        else format(decision.requested_reservation, "f"),
        "snapshot_age": decision.snapshot_age,
        "ledger_revision": int(decision.ledger_revision),
        "pricing_version": decision.pricing_version,
    }


def decision_from_wire(data: Mapping[str, Any]) -> BudgetDecision:
    try:
        return BudgetDecision(
            allowed=data["allowed"],
            kind=BudgetDecisionKind(data["kind"]),
            reason=str(data["reason"]),
            balance=_dec(data.get("balance")),
            active_reservations=_dec(data["active_reservations"]) or Decimal("0"),
            minimum_remaining=_dec(data.get("minimum_remaining")),
            available_to_start=_dec(data.get("available_to_start")),
            requested_reservation=_dec(data.get("requested_reservation")),
            snapshot_age=data.get("snapshot_age"),
            ledger_revision=int(data["ledger_revision"]),
            pricing_version=data.get("pricing_version"),
        )
    except StoreApiError:
        raise
    except Exception:
        raise StoreApiError("decision payload is invalid") from None


def reservation_to_wire(reservation: Reservation) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "run_id": reservation.run_id,
        "reserved": format(reservation.reserved, "f"),
        "state": reservation.state.value,
        "created_at": reservation.created_at.isoformat(),
        "updated_at": reservation.updated_at.isoformat(),
        "actual_cost": None
        if reservation.actual_cost is None
        else format(reservation.actual_cost, "f"),
        "released_amount": None
        if reservation.released_amount is None
        else format(reservation.released_amount, "f"),
        "overspend": None
        if reservation.overspend is None
        else format(reservation.overspend, "f"),
    }


def reservation_from_wire(data: Mapping[str, Any]) -> Reservation:
    try:
        return Reservation(
            id=str(data["id"]),
            run_id=str(data["run_id"]),
            reserved=_dec(data["reserved"]),
            state=ReservationState(data["state"]),
            created_at=_dt(data["created_at"]),
            updated_at=_dt(data["updated_at"]),
            actual_cost=_dec(data.get("actual_cost")),
            released_amount=_dec(data.get("released_amount")),
            overspend=_dec(data.get("overspend")),
        )
    except StoreApiError:
        raise
    except Exception:
        raise StoreApiError("reservation payload is invalid") from None


def admission_to_wire(result: BudgetAdmissionResult) -> dict[str, Any]:
    return {
        "decision": decision_to_wire(result.decision),
        "reservation": None
        if result.reservation is None
        else reservation_to_wire(result.reservation),
    }


def admission_from_wire(data: Mapping[str, Any]) -> BudgetAdmissionResult:
    reservation = data.get("reservation")
    try:
        return BudgetAdmissionResult(
            decision=decision_from_wire(data["decision"]),
            reservation=None if reservation is None else reservation_from_wire(reservation),
        )
    except StoreApiError:
        raise
    except Exception:
        raise StoreApiError("admission payload is invalid") from None


def case_to_wire(case: UsageUnknownCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "run_id": case.run_id,
        "call_id": case.call_id,
        "reservation_id": case.reservation_id,
        "intent": case.intent.value,
        "requested_tier": case.requested_tier.value,
        "effective_tier": None
        if case.effective_tier is None
        else case.effective_tier.value,
        "pricing_version": case.pricing_version,
        "state": case.state.value,
        "revision": case.revision,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "actual_cost_cny": None
        if case.actual_cost_cny is None
        else format(case.actual_cost_cny, "f"),
        "new_call_id": case.new_call_id,
        "prompt_hash": case.prompt_hash,
        "prompt_artifact": case.prompt_artifact,
    }


def case_from_wire(data: Mapping[str, Any]) -> UsageUnknownCase:
    try:
        return UsageUnknownCase(
            case_id=str(data["case_id"]),
            run_id=str(data["run_id"]),
            call_id=str(data["call_id"]),
            reservation_id=str(data["reservation_id"]),
            intent=TaskIntent(data["intent"]),
            requested_tier=ModelTier(data["requested_tier"]),
            effective_tier=None
            if data.get("effective_tier") is None
            else ModelTier(data["effective_tier"]),
            pricing_version=str(data["pricing_version"]),
            state=UsageUnknownState(data["state"]),
            revision=int(data["revision"]),
            created_at=_dt(data["created_at"]),
            updated_at=_dt(data["updated_at"]),
            actual_cost_cny=_dec(data.get("actual_cost_cny")),
            new_call_id=data.get("new_call_id"),
            prompt_hash=data.get("prompt_hash"),
            prompt_artifact=data.get("prompt_artifact"),
        )
    except StoreApiError:
        raise
    except Exception:
        raise StoreApiError("usage-unknown case payload is invalid") from None


class StoreApiClient:
    """Signed JSON client for the console store API."""

    def __init__(
        self,
        base_url: str,
        hmac_key: bytes,
        *,
        timeout: float = 30.0,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise StoreApiError("base_url is invalid")
        if not isinstance(hmac_key, (bytes, bytearray)) or len(hmac_key) < 32:
            raise StoreApiError("hmac_key must be at least 32 bytes")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise StoreApiError("timeout must be positive")
        self._base_url = base_url.strip().rstrip("/")
        self._key = bytes(hmac_key)
        self._timeout = float(timeout)

    def request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        if not path.startswith(STORE_PREFIX):
            raise StoreApiError("store path is invalid")
        url = self._base_url + path
        if params:
            url = url + "?" + urllib.parse.urlencode(sorted(params.items()))
        body = canonical_body(payload) if method != "GET" else b""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        signature = sign_request(self._key, method, path, body, timestamp)
        request = urllib.request.Request(
            url,
            data=body if body else None,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Bogda-Timestamp": str(timestamp),
                "X-Bogda-Signature": signature,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise StoreApiError(
                f"store api {method} {path} failed: HTTP {error.code}"
            ) from None
        except Exception:
            raise StoreApiError(f"store api {method} {path} failed: transport") from None
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise StoreApiError("store api response is not JSON") from None
        if not isinstance(data, dict):
            raise StoreApiError("store api response is not an object")
        return data


class RemoteBudgetService:
    """BudgetAdmissionService-compatible view backed by the console store API."""

    def __init__(self, client: StoreApiClient) -> None:
        self._client = client

    def admit(
        self,
        run_id: str,
        intent: TaskIntent,
        envelope: Any,
        reservation_cny: Decimal | None = None,
        *,
        approval: object | None = None,
    ) -> BudgetAdmissionResult:
        if approval is not None:
            raise StoreApiError(
                "remote budget admission resolves approvals server-side"
            )
        payload = {
            "run_id": run_id,
            "intent": intent.value if isinstance(intent, TaskIntent) else str(intent),
            "envelope": envelope.model_dump(mode="json")
            if hasattr(envelope, "model_dump")
            else envelope,
            "reservation_cny": None
            if reservation_cny is None
            else format(reservation_cny, "f"),
        }
        data = self._client.request("POST", f"{STORE_PREFIX}/budget/admit", payload)
        return admission_from_wire(data["result"])

    def release(
        self,
        reservation_id: str,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
    ) -> Reservation:
        payload = {
            "reservation_id": reservation_id,
            "intent": intent.value if isinstance(intent, TaskIntent) else str(intent),
            "requested_tier": requested_tier.value
            if isinstance(requested_tier, ModelTier)
            else str(requested_tier),
            "pricing_version": pricing_version,
        }
        data = self._client.request("POST", f"{STORE_PREFIX}/budget/release", payload)
        return reservation_from_wire(data["reservation"])

    def reconcile(
        self,
        reservation_id: str,
        actual_cost_cny: Decimal,
        *,
        intent: TaskIntent,
        requested_tier: ModelTier,
        pricing_version: str,
    ) -> Reservation:
        payload = {
            "reservation_id": reservation_id,
            "actual_cost_cny": format(actual_cost_cny, "f"),
            "intent": intent.value if isinstance(intent, TaskIntent) else str(intent),
            "requested_tier": requested_tier.value
            if isinstance(requested_tier, ModelTier)
            else str(requested_tier),
            "pricing_version": pricing_version,
        }
        data = self._client.request("POST", f"{STORE_PREFIX}/budget/reconcile", payload)
        return reservation_from_wire(data["reservation"])

    def catalog_for(self, version: str) -> Any:
        catalog = catalog_registry().get(version)
        if catalog is None:
            raise StoreApiError("unknown pricing version")
        return catalog


class RemoteUsageUnknownRecovery:
    """UsageUnknownRecoveryPort backed by the console store API."""

    def __init__(self, client: StoreApiClient) -> None:
        self._client = client

    def open_case(
        self,
        *,
        run_id: str,
        call_id: str,
        reservation_id: str,
        intent: TaskIntent,
        requested_tier: ModelTier,
        effective_tier: ModelTier | None = None,
        pricing_version: str,
        prompt_hash: str | None = None,
        prompt_artifact: str | None = None,
        case_id: str | None = None,
    ) -> UsageUnknownCase:
        payload = {
            "run_id": run_id,
            "call_id": call_id,
            "reservation_id": reservation_id,
            "intent": intent.value if isinstance(intent, TaskIntent) else str(intent),
            "requested_tier": requested_tier.value
            if isinstance(requested_tier, ModelTier)
            else str(requested_tier),
            "effective_tier": None
            if effective_tier is None
            else (effective_tier.value if isinstance(effective_tier, ModelTier) else str(effective_tier)),
            "pricing_version": pricing_version,
            "prompt_hash": prompt_hash,
            "prompt_artifact": prompt_artifact,
            "case_id": case_id,
        }
        data = self._client.request(
            "POST", f"{STORE_PREFIX}/usage-unknown/cases", payload
        )
        return case_from_wire(data["case"])

    def blocks_original_call(self, run_id: str, call_id: str) -> bool:
        data = self._client.request(
            "GET",
            f"{STORE_PREFIX}/usage-unknown/blocked",
            params={"run_id": run_id, "call_id": call_id},
        )
        return bool(data.get("blocked"))


__all__ = [
    "API_DOMAIN",
    "REPLAY_WINDOW_SECONDS",
    "STORE_PREFIX",
    "RemoteBudgetService",
    "RemoteUsageUnknownRecovery",
    "StoreApiClient",
    "StoreApiError",
    "admission_from_wire",
    "admission_to_wire",
    "canonical_body",
    "case_from_wire",
    "case_to_wire",
    "decision_from_wire",
    "decision_to_wire",
    "reservation_from_wire",
    "reservation_to_wire",
    "sign_request",
    "verify_request",
]
