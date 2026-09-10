import json
import threading
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from bogda.budget.guard import BudgetDecision, BudgetDecisionKind
from bogda.budget.ledger import Reservation, ReservationState
from bogda.budget.service import BudgetAdmissionResult
from bogda.contracts import ModelTier, TaskIntent
from bogda.model_runtime.recovery import UsageUnknownCase, UsageUnknownState
from bogda.wiring.store_api import (
    RemoteBudgetService,
    RemoteUsageUnknownRecovery,
    StoreApiClient,
    StoreApiError,
    admission_from_wire,
    admission_to_wire,
    case_from_wire,
    case_to_wire,
    sign_request,
    verify_request,
)

KEY = bytes.fromhex("ab" * 32)
NOW = int(datetime.now(timezone.utc).timestamp())


def _decision(allowed=True, kind=BudgetDecisionKind.ALLOW):
    return BudgetDecision(
        allowed=allowed,
        kind=kind,
        reason="allow" if allowed else "owner_approval_required",
        balance=Decimal("12.50") if allowed else None,
        active_reservations=Decimal("0"),
        minimum_remaining=None,
        available_to_start=Decimal("12.00") if allowed else None,
        requested_reservation=Decimal("0.50") if allowed else None,
        snapshot_age=5,
        ledger_revision=3,
        pricing_version="deepseek-cn-2026-08-28",
    )


def _reservation():
    stamp = datetime.now(timezone.utc)
    return Reservation(
        id="reservation-1",
        run_id="run-1",
        reserved=Decimal("0.50"),
        state=ReservationState.ACTIVE,
        created_at=stamp,
        updated_at=stamp,
    )


def _case():
    stamp = datetime.now(timezone.utc)
    return UsageUnknownCase(
        case_id="case-1",
        run_id="run-1",
        call_id="call-1",
        reservation_id="reservation-1",
        intent=TaskIntent.EXECUTE,
        requested_tier=ModelTier.FLASH,
        effective_tier=ModelTier.FLASH,
        pricing_version="deepseek-cn-2026-08-28",
        state=UsageUnknownState.AWAITING_RECONCILIATION,
        revision=0,
        created_at=stamp,
        updated_at=stamp,
    )


def test_sign_and_verify_roundtrip_rejects_tampering() -> None:
    body = b'{"a":1}'
    signature = sign_request(KEY, "POST", "/api/v1/store/x", body, NOW)

    verify_request(KEY, "POST", "/api/v1/store/x", body, NOW, signature, now_epoch=NOW)

    with pytest.raises(StoreApiError, match="signature mismatch"):
        verify_request(KEY, "POST", "/api/v1/store/x", b'{"a":2}', NOW, signature, now_epoch=NOW)
    with pytest.raises(StoreApiError, match="signature mismatch"):
        verify_request(b"b" * 32, "POST", "/api/v1/store/x", body, NOW, signature, now_epoch=NOW)


def test_verify_rejects_stale_timestamp() -> None:
    signature = sign_request(KEY, "GET", "/api/v1/store/y", b"", NOW)
    with pytest.raises(StoreApiError, match="replay window"):
        verify_request(KEY, "GET", "/api/v1/store/y", b"", NOW, signature, now_epoch=NOW + 301)


def test_admission_result_roundtrip_preserves_fields() -> None:
    admitted = BudgetAdmissionResult(decision=_decision(), reservation=_reservation())
    decoded = admission_from_wire(admission_to_wire(admitted))

    assert decoded.decision.allowed is True
    assert decoded.decision.kind is BudgetDecisionKind.ALLOW
    assert decoded.decision.balance == Decimal("12.50")
    assert decoded.reservation is not None
    assert decoded.reservation.id == "reservation-1"
    assert decoded.reservation.reserved == Decimal("0.50")
    assert decoded.reservation.state is ReservationState.ACTIVE


def test_denied_admission_roundtrip_has_no_reservation() -> None:
    denied = BudgetAdmissionResult(
        decision=_decision(allowed=False, kind=BudgetDecisionKind.OWNER_APPROVAL_REQUIRED)
    )
    decoded = admission_from_wire(admission_to_wire(denied))

    assert decoded.decision.allowed is False
    assert decoded.decision.kind is BudgetDecisionKind.OWNER_APPROVAL_REQUIRED
    assert decoded.reservation is None


def test_usage_unknown_case_roundtrip_preserves_fields() -> None:
    original = _case()
    decoded = case_from_wire(case_to_wire(original))

    assert decoded == original


class _StoreHandler(BaseHTTPRequestHandler):
    admission = BudgetAdmissionResult(decision=_decision(), reservation=_reservation())
    blocked = True

    def log_message(self, *args):  # silence
        pass

    def _authorized(self, body: bytes) -> bool:
        ts = self.headers.get("X-Bogda-Timestamp")
        sig = self.headers.get("X-Bogda-Signature")
        try:
            verify_request(
                KEY,
                self.command,
                urlparse(self.path).path,
                body,
                int(ts),
                sig or "",
                now_epoch=int(datetime.now(timezone.utc).timestamp()),
            )
        except Exception:
            return False
        return True

    def _respond(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if not self._authorized(b""):
            self._respond(401, {"detail": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path.endswith("/usage-unknown/blocked"):
            self._respond(200, {"blocked": self.blocked})
            return
        self._respond(404, {"detail": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        if not self._authorized(body):
            self._respond(401, {"detail": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path.endswith("/budget/admit"):
            self._respond(200, {"result": admission_to_wire(self.admission)})
            return
        self._respond(404, {"detail": "not found"})


@pytest.fixture()
def store_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StoreHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_remote_budget_and_recovery_against_real_http(store_server) -> None:
    client = StoreApiClient(store_server, KEY)
    budget = RemoteBudgetService(client)
    recovery = RemoteUsageUnknownRecovery(client)

    from bogda.contracts import BudgetSource, RunBudgetEnvelope

    envelope = RunBudgetEnvelope(
        expected_cost=Decimal("0.10"),
        authorized_ceiling=Decimal("1"),
        minimum_remaining=Decimal("0"),
        requested_tier=ModelTier.FLASH,
        fallback_tier=None,
        budget_source=BudgetSource.RUN,
        pricing_version="deepseek-cn-2026-08-28",
    )
    admission = budget.admit("run-1", TaskIntent.EXECUTE, envelope)
    assert admission.decision.allowed is True
    assert admission.reservation is not None

    assert recovery.blocks_original_call("run-1", "call-1") is True

    assert budget.catalog_for("deepseek-cn-2026-08-28").version == "deepseek-cn-2026-08-28"
    with pytest.raises(StoreApiError, match="unknown pricing version"):
        budget.catalog_for("other")


def test_remote_client_rejects_bad_signature_server(store_server) -> None:
    wrong_key_client = StoreApiClient(store_server, b"c" * 32)
    with pytest.raises(StoreApiError, match="HTTP 401"):
        RemoteUsageUnknownRecovery(wrong_key_client).blocks_original_call("run-1", "call-1")
