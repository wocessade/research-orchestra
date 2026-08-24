from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

import pytest

from bogda.ops.snapshot import create_snapshot, verify_snapshot


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    source = tmp_path / "prefect.db"
    with sqlite3.connect(source) as connection:
        connection.execute("create table runs (id TEXT PRIMARY KEY, result TEXT)")
        connection.execute("insert into runs values ('r1', 'accepted')")
    return source


def test_snapshot_can_be_verified_and_read(source_db: Path, tmp_path: Path) -> None:
    report = create_snapshot(
        source_db,
        tmp_path / "snapshots",
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )

    snapshot = Path(report["snapshot"])
    manifest = Path(report["manifest"])
    assert snapshot.name == "prefect-20260824T120000Z.db"
    assert snapshot.is_file()
    assert manifest == snapshot.with_suffix(".json")
    assert manifest.is_file()
    assert (snapshot.parent / "latest.json").is_file()

    saved_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved_manifest["sha256"] == report["sha256"]
    assert saved_manifest["bytes"] == snapshot.stat().st_size
    assert saved_manifest["integrity_check"] == "ok"
    assert json.loads((snapshot.parent / "latest.json").read_text(encoding="utf-8")) == saved_manifest

    verified = verify_snapshot(snapshot, manifest, tmp_path / "restore")
    assert verified["sha256"] == report["sha256"]
    assert verified["integrity_check"] == "ok"
    with sqlite3.connect(verified["restored_path"]) as connection:
        assert connection.execute("select result from runs where id='r1'").fetchone() == ("accepted",)


def test_corrupt_source_does_not_replace_previous_latest(source_db: Path, tmp_path: Path) -> None:
    destination = tmp_path / "snapshots"
    first = create_snapshot(
        source_db,
        destination,
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    latest_before = (destination / "latest.json").read_bytes()
    source_db.write_bytes(b"not a sqlite database")

    with pytest.raises(sqlite3.DatabaseError):
        create_snapshot(
            source_db,
            destination,
            now=datetime(2026, 8, 24, 13, tzinfo=UTC),
        )

    assert (destination / "latest.json").read_bytes() == latest_before
    assert Path(first["snapshot"]).is_file()


def test_keep_prunes_oldest_snapshot_pairs(source_db: Path, tmp_path: Path) -> None:
    destination = tmp_path / "snapshots"
    for hour in (12, 13, 14):
        create_snapshot(
            source_db,
            destination,
            keep=2,
            now=datetime(2026, 8, 24, hour, tzinfo=UTC),
        )

    assert sorted(path.name for path in destination.glob("*.db")) == [
        "prefect-20260824T130000Z.db",
        "prefect-20260824T140000Z.db",
    ]
    assert sorted(path.name for path in destination.glob("*.json")) == [
        "latest.json",
        "prefect-20260824T130000Z.json",
        "prefect-20260824T140000Z.json",
    ]
