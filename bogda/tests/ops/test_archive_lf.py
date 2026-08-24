from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PI_PREFIX = "bogda/deploy/pi"
EXPECTED_SCRIPTS = ("install.sh", "rollback.sh")
EXPECTED_UNITS = {
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
}


def _archive_pi_deploy(destination: Path) -> None:
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar",
            "-o",
            str(destination),
            "HEAD",
            PI_PREFIX,
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def _archived_files(archive: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with tarfile.open(archive, "r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            assert extracted is not None
            files[member.name.replace("\\", "/")] = extracted.read()
    return files


def test_gitattributes_force_lf_on_pi_shell_and_units() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "bogda/deploy/pi/*.sh text eol=lf" in attributes
    assert "bogda/deploy/pi/systemd/* text eol=lf" in attributes


def test_git_archive_pi_shell_and_units_are_lf(tmp_path: Path) -> None:
    archive = tmp_path / "pi.tar"
    _archive_pi_deploy(archive)
    files = _archived_files(archive)

    scripts = {
        Path(name).name: payload
        for name, payload in files.items()
        if name.endswith(".sh")
    }
    units = {
        Path(name).name: payload
        for name, payload in files.items()
        if "/systemd/" in name
    }

    assert set(scripts) == set(EXPECTED_SCRIPTS)
    assert set(units) == EXPECTED_UNITS

    for name, payload in {**scripts, **units}.items():
        assert b"\r" not in payload, name


def test_archived_install_and_rollback_parse_as_unix_shell(tmp_path: Path) -> None:
    archive = tmp_path / "pi.tar"
    _archive_pi_deploy(archive)
    with tarfile.open(archive, "r") as tar:
        tar.extractall(tmp_path / "unpacked")

    install = tmp_path / "unpacked" / PI_PREFIX / "install.sh"
    rollback = tmp_path / "unpacked" / PI_PREFIX / "rollback.sh"
    for script in (install, rollback):
        text = script.read_bytes()
        assert text.startswith(b"#!/usr/bin/env bash\n")
        assert b"\r" not in text

    bash = os.environ.get("BOGDA_BASH")
    if not bash:
        pytest.skip("BOGDA_BASH is required for bash -n")
    for script in (install, rollback):
        subprocess.run([bash, "-n", str(script)], check=True)
