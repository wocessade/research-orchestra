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
def checkout_copy(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    shutil.copytree(
        DEPLOY_ROOT.parents[1] / "src",
        checkout / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(DEPLOY_ROOT, checkout / "deploy" / "pi")
    return checkout


def test_shell_syntax() -> None:
    bash = os.environ["BOGDA_BASH"]
    for script in (INSTALL, ROLLBACK):
        subprocess.run([bash, "-n", str(script)], check=True)


@pytest.mark.parametrize("script_name", ["install.sh", "rollback.sh"])
def test_dry_run_preserves_checkout_and_stays_within_bogda_boundary(
    checkout_copy: Path, script_name: str
) -> None:
    before = tree_hashes(checkout_copy)
    bundle_copy = checkout_copy / "deploy" / "pi"

    result = subprocess.run(
        [os.environ["BOGDA_BASH"], str(bundle_copy / script_name), "--dry-run"],
        cwd=bundle_copy,
        text=True,
        capture_output=True,
        check=True,
    )

    assert tree_hashes(checkout_copy) == before
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


def test_install_checks_start_auth_before_host_mutations() -> None:
    source = INSTALL.read_text(encoding="utf-8")

    assert "start_env=" in source
    assert source.index("start_env=") < source.index("if ! getent passwd bogda")
    assert 'grep -F -q "SET_ON_PI_NOT_IN_GIT" "$start_env"' in source


def test_rollback_validates_inventory_before_state_changes() -> None:
    source = ROLLBACK.read_text(encoding="utf-8")

    assert "validate_inventory()" in source
    assert "apply_inventory()" in source
    assert source.index("\nvalidate_inventory\n") < source.index("systemctl disable --now")
    assert source.index("systemctl disable --now") < source.index("\napply_inventory\n")
    assert '[ -L "$target" ]' in source
    assert '[ -L "$backup_file" ] || [ ! -f "$backup_file" ]' in source
    assert "backup_parent=" in source
