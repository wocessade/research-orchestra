from __future__ import annotations

from datetime import UTC, datetime
import json
import os
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


def test_verify_rejects_existing_restore_target_without_overwriting(
    source_db: Path, tmp_path: Path
) -> None:
    report = create_snapshot(
        source_db,
        tmp_path / "snapshots",
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    restore_dir = tmp_path / "restore"
    restore_dir.mkdir()
    restored = restore_dir / "prefect-restored.db"
    original = b"caller-owned restore"
    restored.write_bytes(original)

    with pytest.raises(FileExistsError):
        verify_snapshot(Path(report["snapshot"]), Path(report["manifest"]), restore_dir)

    assert restored.read_bytes() == original


def test_verify_rejects_symlink_restore_target_without_following_it(
    source_db: Path, tmp_path: Path
) -> None:
    report = create_snapshot(
        source_db,
        tmp_path / "snapshots",
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    restore_dir = tmp_path / "restore"
    restore_dir.mkdir()
    outside = tmp_path / "live.db"
    original = b"live database"
    outside.write_bytes(original)
    restored = restore_dir / "prefect-restored.db"
    try:
        os.symlink(outside, restored)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    with pytest.raises(FileExistsError):
        verify_snapshot(Path(report["snapshot"]), Path(report["manifest"]), restore_dir)

    assert outside.read_bytes() == original
    assert restored.is_symlink()


def test_pruning_complete_pairs_does_not_consume_orphan_database(
    source_db: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "snapshots"
    create_snapshot(
        source_db,
        destination,
        keep=2,
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    create_snapshot(
        source_db,
        destination,
        keep=2,
        now=datetime(2026, 8, 24, 13, tzinfo=UTC),
    )
    orphan = destination / "prefect-20260824T110000Z.db"
    orphan.write_bytes(b"unrelated evidence")

    create_snapshot(
        source_db,
        destination,
        keep=2,
        now=datetime(2026, 8, 24, 14, tzinfo=UTC),
    )

    assert orphan.read_bytes() == b"unrelated evidence"
    assert (destination / "prefect-20260824T130000Z.db").is_file()
    assert (destination / "prefect-20260824T130000Z.json").is_file()
    assert (destination / "prefect-20260824T140000Z.db").is_file()
    assert (destination / "prefect-20260824T140000Z.json").is_file()


def test_non_monotonic_timestamp_is_rejected_without_dangling_latest(
    source_db: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "snapshots"
    first = create_snapshot(
        source_db,
        destination,
        keep=1,
        now=datetime(2026, 8, 24, 14, tzinfo=UTC),
    )
    latest_before = (destination / "latest.json").read_bytes()

    with pytest.raises(ValueError, match="timestamp"):
        create_snapshot(
            source_db,
            destination,
            keep=1,
            now=datetime(2026, 8, 24, 13, tzinfo=UTC),
        )

    assert (destination / "latest.json").read_bytes() == latest_before
    assert Path(first["snapshot"]).is_file()
    assert not (destination / "prefect-20260824T130000Z.db").exists()


def test_same_second_timestamp_is_rejected_without_overwriting_snapshot(
    source_db: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "snapshots"
    first = create_snapshot(
        source_db,
        destination,
        now=datetime(2026, 8, 24, 12, tzinfo=UTC),
    )
    snapshot = Path(first["snapshot"])
    manifest = Path(first["manifest"])
    snapshot_before = snapshot.read_bytes()
    manifest_before = manifest.read_bytes()
    latest_before = (destination / "latest.json").read_bytes()

    with pytest.raises(ValueError, match="already exists"):
        create_snapshot(
            source_db,
            destination,
            now=datetime(2026, 8, 24, 12, tzinfo=UTC),
        )

    assert snapshot.read_bytes() == snapshot_before
    assert manifest.read_bytes() == manifest_before
    assert (destination / "latest.json").read_bytes() == latest_before
