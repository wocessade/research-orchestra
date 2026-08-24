"""Consistent local SQLite snapshots and restore verification."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from typing import Any


_SNAPSHOT_NAME = re.compile(r"^prefect-\d{8}T\d{6}Z\.db$")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of *path* as a lowercase hexadecimal string."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def integrity_check(path: Path) -> str:
    """Run SQLite's integrity check against *path* in read-only mode."""
    connection = sqlite3.connect(_read_only_uri(path), uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if result is None:
        raise sqlite3.DatabaseError(f"integrity check returned no result: {path}")
    return str(result[0])


def _temporary_path(destination: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=destination)
    os.close(descriptor)
    return Path(name)


def _atomic_json_write(path: Path, data: dict[str, object]) -> None:
    temporary = _temporary_path(path.parent, f".{path.name}.")
    try:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n"
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def create_snapshot(
    source: Path,
    destination: Path,
    keep: int = 7,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create and publish a consistent snapshot of a local SQLite database."""
    if keep < 1:
        raise ValueError("keep must be at least 1")

    source = Path(source)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    created = _utc_now(now)
    timestamp = created.strftime("%Y%m%dT%H%M%SZ")
    snapshot = destination / f"prefect-{timestamp}.db"
    manifest = snapshot.with_suffix(".json")
    temporary_db: Path | None = None

    try:
        source_integrity = integrity_check(source)
        if source_integrity != "ok":
            raise sqlite3.DatabaseError(f"source integrity check failed: {source_integrity}")

        temporary_db = _temporary_path(destination, f".{snapshot.name}.")
        source_connection = sqlite3.connect(_read_only_uri(source), uri=True)
        destination_connection = sqlite3.connect(temporary_db)
        try:
            try:
                source_connection.backup(destination_connection)
                destination_connection.commit()
            finally:
                destination_connection.close()
        finally:
            source_connection.close()
        temporary_integrity = integrity_check(temporary_db)
        if temporary_integrity != "ok":
            raise sqlite3.DatabaseError(
                f"temporary snapshot integrity check failed: {temporary_integrity}"
            )
        temporary_db.replace(snapshot)
        temporary_db = None

        snapshot_integrity = integrity_check(snapshot)
        if snapshot_integrity != "ok":
            raise sqlite3.DatabaseError(f"snapshot integrity check failed: {snapshot_integrity}")
        manifest_data: dict[str, object] = {
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "source": str(source),
            "snapshot": str(snapshot),
            "bytes": snapshot.stat().st_size,
            "sha256": sha256_file(snapshot),
            "integrity_check": snapshot_integrity,
            "tool_version": "1",
        }
        _atomic_json_write(manifest, manifest_data)
        _atomic_json_write(destination / "latest.json", manifest_data)
        prune_snapshots(destination, keep)
        report = {**manifest_data, "manifest": str(manifest)}
        return report
    except Exception:
        if temporary_db is not None:
            temporary_db.unlink(missing_ok=True)
        raise


def verify_snapshot(
    snapshot: Path,
    manifest: Path,
    restore_dir: Path,
) -> dict[str, object]:
    """Verify a snapshot manifest, restore it to a caller-owned directory, and check it."""
    snapshot = Path(snapshot)
    manifest = Path(manifest)
    restore_dir = Path(restore_dir)
    try:
        recorded: Any = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid snapshot manifest: {manifest}") from error
    if not isinstance(recorded, dict):
        raise ValueError(f"invalid snapshot manifest: {manifest}")
    if recorded.get("snapshot") != str(snapshot):
        raise ValueError("snapshot manifest does not name the requested snapshot")
    if not snapshot.is_file():
        raise ValueError(f"snapshot does not exist: {snapshot}")
    actual_bytes = snapshot.stat().st_size
    actual_sha256 = sha256_file(snapshot)
    if recorded.get("bytes") != actual_bytes:
        raise ValueError("snapshot byte count does not match manifest")
    if recorded.get("sha256") != actual_sha256:
        raise ValueError("snapshot SHA-256 does not match manifest")

    restore_dir.mkdir(parents=True, exist_ok=True)
    restored = restore_dir / "prefect-restored.db"
    shutil.copyfile(snapshot, restored)
    checked = integrity_check(restored)
    if checked != "ok":
        raise sqlite3.DatabaseError(f"restored snapshot integrity check failed: {checked}")
    return {
        "snapshot": str(snapshot),
        "manifest": str(manifest),
        "restored_path": str(restored),
        "bytes": actual_bytes,
        "sha256": actual_sha256,
        "integrity_check": checked,
    }


def prune_snapshots(destination: Path, keep: int) -> tuple[Path, ...]:
    """Remove the oldest timestamped snapshot pairs, preserving ``latest.json``."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    destination = Path(destination)
    snapshots = sorted(
        (path for path in destination.glob("prefect-*.db") if _SNAPSHOT_NAME.match(path.name)),
        key=lambda path: path.name,
    )
    removed: list[Path] = []
    while len(snapshots) > keep:
        snapshot = snapshots.pop(0)
        adjacent_manifest = snapshot.with_suffix(".json")
        snapshot.unlink(missing_ok=True)
        removed.append(snapshot)
        if adjacent_manifest.exists():
            adjacent_manifest.unlink()
            removed.append(adjacent_manifest)
    return tuple(removed)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bogda.ops.snapshot")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("--source", required=True, type=Path)
    create.add_argument("--destination", required=True, type=Path)
    create.add_argument("--keep", type=int, default=7)

    verify = commands.add_parser("verify")
    verify.add_argument("--snapshot", required=True, type=Path)
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--restore-dir", required=True, type=Path)
    args = parser.parse_args(arguments)

    try:
        if args.command == "create":
            report = create_snapshot(args.source, args.destination, args.keep)
        else:
            report = verify_snapshot(args.snapshot, args.manifest, args.restore_dir)
    except Exception as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
