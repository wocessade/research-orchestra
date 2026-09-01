"""Single-use owner approval credentials for envelopes above 20 CNY."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from sqlite3 import Connection, connect
from threading import RLock
from typing import Callable
from uuid import uuid4

from bogda.contracts import RunBudgetEnvelope


class ApprovalError(ValueError):
    """The credential is missing, forged, expired, mismatched, or already used."""


@dataclass(frozen=True, slots=True)
class OwnerApprovalCredential:
    credential_id: str
    run_id: str
    envelope_digest: str
    pricing_version: str
    authorized_ceiling_cny: Decimal
    actor_id: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    mac: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS owner_approvals (
    credential_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    envelope_digest TEXT NOT NULL,
    pricing_version TEXT NOT NULL,
    authorized_ceiling_cny TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    nonce TEXT NOT NULL,
    mac TEXT NOT NULL,
    consumed_at TEXT
);
"""


def envelope_digest(envelope: RunBudgetEnvelope) -> str:
    if not isinstance(envelope, RunBudgetEnvelope):
        raise ApprovalError("envelope is invalid")
    canonical = json.dumps(
        envelope.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ApprovalError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _mac_message(credential: OwnerApprovalCredential) -> bytes:
    ceiling = format(credential.authorized_ceiling_cny, "f")
    payload = "|".join(
        (
            credential.credential_id,
            credential.run_id,
            credential.envelope_digest,
            credential.pricing_version,
            ceiling,
            credential.actor_id,
            credential.issued_at.isoformat(),
            credential.expires_at.isoformat(),
            credential.nonce,
        )
    )
    return payload.encode("utf-8")


class SqliteApprovalStore:
    def __init__(
        self,
        path: Path,
        *,
        hmac_key: bytes,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(path, Path):
            raise ApprovalError("path must be a Path")
        if not isinstance(hmac_key, (bytes, bytearray)) or not hmac_key:
            raise ApprovalError("hmac_key is invalid")
        if clock is not None and not callable(clock):
            raise ApprovalError("clock must be callable")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._key = bytes(hmac_key)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._lock = RLock()
        self._conn: Connection = connect(path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _now(self) -> datetime:
        return _aware(self._clock(), "timestamp")

    def _sign(self, credential: OwnerApprovalCredential) -> str:
        return hmac.new(self._key, _mac_message(credential), hashlib.sha256).hexdigest()

    def issue(
        self,
        *,
        run_id: str,
        envelope: RunBudgetEnvelope,
        actor_id: str,
        ttl: timedelta,
    ) -> OwnerApprovalCredential:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ApprovalError("run_id is invalid")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ApprovalError("actor_id is invalid")
        if not isinstance(ttl, timedelta) or ttl.total_seconds() < 0:
            raise ApprovalError("ttl is invalid")
        issued_at = self._now()
        unsigned = OwnerApprovalCredential(
            credential_id=str(self._id_factory()),
            run_id=run_id.strip(),
            envelope_digest=envelope_digest(envelope),
            pricing_version=envelope.pricing_version,
            authorized_ceiling_cny=envelope.authorized_ceiling,
            actor_id=actor_id.strip(),
            issued_at=issued_at,
            expires_at=issued_at + ttl,
            nonce=uuid4().hex,
            mac="",
        )
        credential = replace(unsigned, mac=self._sign(unsigned))
        with self._lock:
            self._conn.execute(
                "INSERT INTO owner_approvals ("
                "credential_id, run_id, envelope_digest, pricing_version, "
                "authorized_ceiling_cny, actor_id, issued_at, expires_at, nonce, mac"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    credential.credential_id,
                    credential.run_id,
                    credential.envelope_digest,
                    credential.pricing_version,
                    format(credential.authorized_ceiling_cny, "f"),
                    credential.actor_id,
                    credential.issued_at.isoformat(),
                    credential.expires_at.isoformat(),
                    credential.nonce,
                    credential.mac,
                ),
            )
            self._conn.commit()
        return credential

    def _row_to_credential(self, row: tuple[object, ...]) -> OwnerApprovalCredential:
        return OwnerApprovalCredential(
            credential_id=str(row[0]),
            run_id=str(row[1]),
            envelope_digest=str(row[2]),
            pricing_version=str(row[3]),
            authorized_ceiling_cny=Decimal(str(row[4])),
            actor_id=str(row[5]),
            issued_at=datetime.fromisoformat(str(row[6])),
            expires_at=datetime.fromisoformat(str(row[7])),
            nonce=str(row[8]),
            mac=str(row[9]),
        )

    def get_open(self, run_id: str) -> OwnerApprovalCredential | None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ApprovalError("run_id is invalid")
        with self._lock:
            row = self._conn.execute(
                "SELECT credential_id, run_id, envelope_digest, pricing_version, "
                "authorized_ceiling_cny, actor_id, issued_at, expires_at, nonce, mac "
                "FROM owner_approvals WHERE run_id = ? AND consumed_at IS NULL "
                "ORDER BY issued_at DESC LIMIT 1",
                (run_id.strip(),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_credential(row)

    def consume_open(
        self,
        *,
        run_id: str,
        envelope: RunBudgetEnvelope,
    ) -> OwnerApprovalCredential:
        credential = self.get_open(run_id)
        if credential is None:
            raise ApprovalError("credential is unknown")
        return self.consume(credential, envelope=envelope, run_id=run_id)

    def consume(
        self,
        credential: OwnerApprovalCredential,
        *,
        envelope: RunBudgetEnvelope,
        run_id: str,
    ) -> OwnerApprovalCredential:
        if not isinstance(credential, OwnerApprovalCredential):
            raise ApprovalError("credential is invalid")
        now = self._now()
        if credential.run_id != run_id:
            raise ApprovalError("run_id does not match")
        if envelope_digest(envelope) != credential.envelope_digest:
            raise ApprovalError("envelope does not match")
        if envelope.pricing_version != credential.pricing_version:
            raise ApprovalError("pricing_version does not match")
        expected_mac = self._sign(replace(credential, mac=""))
        if not hmac.compare_digest(expected_mac, credential.mac):
            raise ApprovalError("mac is invalid")
        if credential.expires_at <= now:
            raise ApprovalError("credential is expired")
        with self._lock:
            row = self._conn.execute(
                "SELECT consumed_at FROM owner_approvals WHERE credential_id = ?",
                (credential.credential_id,),
            ).fetchone()
            if row is None:
                raise ApprovalError("credential is unknown")
            if row[0] is not None:
                raise ApprovalError("credential is already consumed")
            cursor = self._conn.execute(
                "UPDATE owner_approvals SET consumed_at = ? "
                "WHERE credential_id = ? AND consumed_at IS NULL",
                (now.isoformat(), credential.credential_id),
            )
            if cursor.rowcount != 1:
                raise ApprovalError("credential is already consumed")
            self._conn.commit()
        return credential
