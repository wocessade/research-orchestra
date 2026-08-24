from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("BOGDA_BASH"),
    reason="BOGDA_BASH is required for shell checks",
)


DEPLOY_ROOT = Path(__file__).parents[2] / "deploy" / "pi"
INSTALL = DEPLOY_ROOT / "install.sh"
ROLLBACK = DEPLOY_ROOT / "rollback.sh"
EXPECTED_UNITS = {
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
}


def tree_hashes(root: Path) -> dict[Path, str]:
    return {
        path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def bundle_copy(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    shutil.copytree(DEPLOY_ROOT.parents[1] / "src", checkout / "src")
    destination = checkout / "deploy" / "pi"
    destination.parent.mkdir(parents=True)
    shutil.copytree(DEPLOY_ROOT, destination)
    return destination


def test_shell_syntax() -> None:
    bash = os.environ["BOGDA_BASH"]
    for script in (INSTALL, ROLLBACK):
        subprocess.run([bash, "-n", str(script)], check=True)


@pytest.mark.parametrize("script_name", ["install.sh", "rollback.sh"])
def test_dry_run_preserves_bundle_and_stays_within_bogda_boundary(
    bundle_copy: Path, script_name: str
) -> None:
    before = tree_hashes(bundle_copy)

    result = subprocess.run(
        [os.environ["BOGDA_BASH"], str(bundle_copy / script_name), "--dry-run"],
        cwd=bundle_copy,
        text=True,
        capture_output=True,
        check=True,
    )

    assert tree_hashes(bundle_copy) == before
    assert "/mnt/nas/.bogda" in result.stdout
    assert "PRESERVE" in result.stdout
    assert "orchestra" not in result.stdout.lower()
    assert "systemctl " not in result.stdout
    mentioned_units = {
        Path(token).name
        for token in result.stdout.split()
        if token.endswith((".service", ".timer"))
    }
    assert mentioned_units == EXPECTED_UNITS
