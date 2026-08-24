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

    assert "validate_runtime_env()" in source
    assert "PREFECT_HOME=/mnt/nas/.bogda/prefect" in source
    assert "PREFECT_API_URL=http://127.0.0.1:4200/api" in source
    assert "PREFECT_SERVER_API_AUTH_STRING" in source
    assert "PREFECT_API_AUTH_STRING" in source
    assert "--start-server" in source
    assert "--start-services" in source
    assert source.index("validate_runtime_env /etc/bogda/bogda.env") < source.index(
        "if ! getent passwd bogda"
    )


def test_install_prevalidates_literal_managed_paths_before_root_mutations() -> None:
    source = INSTALL.read_text(encoding="utf-8")

    assert "validate_managed_targets()" in source
    assert "/etc/bogda/bogda.env" in source
    assert "/etc/bogda/last-backup" in source
    assert "[ -L \"$target\" ]" in source
    install_mode = source.index('if [ "$mode" = install ]; then')
    assert source.index("validate_managed_targets", install_mode) < source.index(
        "if ! getent passwd bogda"
    )


def test_start_only_modes_are_separate_from_backup_and_install_paths() -> None:
    source = INSTALL.read_text(encoding="utf-8")

    staged_start = source.index(
        'if [ "$mode" = start-server ] || [ "$mode" = start-services ]; then'
    )
    start_server = source.index('if [ "$mode" = start-server ]; then', staged_start)
    backup = source.index('backup_dir="/etc/bogda/backups/')
    sync = source.index("UV_PROJECT_ENVIRONMENT=/opt/bogda/.venv uv sync")
    assert staged_start < start_server < backup
    assert "must be active before --start-services" in source
    assert start_server < sync
    assert staged_start < sync


def test_runtime_auth_preflight_requires_exact_matching_nonsecret_assignments(
    tmp_path: Path,
) -> None:
    source = INSTALL.read_text(encoding="utf-8")
    start = source.index("validate_runtime_env() {")
    end = source.index("\nvalidate_managed_targets()", start)
    validator = tmp_path / "validate-runtime-env.sh"
    validator.write_text(
        "#!/usr/bin/env bash\nset -eu\n"
        + source[start:end]
        + "\nvalidate_runtime_env \"$1\"\n",
        encoding="utf-8",
    )
    valid = tmp_path / "valid.env"
    valid.write_bytes(
        b"PREFECT_HOME=/mnt/nas/.bogda/prefect\n"
        b"PREFECT_API_URL=http://127.0.0.1:4200/api\n"
        b"PREFECT_SERVER_API_AUTH_STRING=alice:matched-secret\n"
        b"PREFECT_API_AUTH_STRING=alice:matched-secret\n"
    )

    assert subprocess.run(
        [os.environ["BOGDA_BASH"], str(validator), str(valid)],
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0

    for invalid_lines in (
        valid.read_text(encoding="utf-8").replace(
            "PREFECT_HOME=/mnt/nas/.bogda/prefect",
            "PREFECT_HOME=/mnt/nas/.bogda/other",
        ),
        valid.read_text(encoding="utf-8").replace(
            "PREFECT_API_URL=http://127.0.0.1:4200/api",
            "PREFECT_API_URL=http://127.0.0.1:9999/api",
        ),
        valid.read_text(encoding="utf-8").replace(
            "PREFECT_API_AUTH_STRING=alice:matched-secret",
            "PREFECT_API_AUTH_STRING=alice:different-secret",
        ),
        valid.read_text(encoding="utf-8").replace(
            "alice:matched-secret", "SET_ON_PI_NOT_IN_GIT"
        ),
        valid.read_text(encoding="utf-8") + "UNRELATED_FLAG=true\n",
        valid.read_text(encoding="utf-8") + "PREFECT_HOME=/mnt/nas/.bogda/prefect\n",
        valid.read_text(encoding="utf-8").replace(
            "PREFECT_SERVER_API_AUTH_STRING=alice:matched-secret",
            "PREFECT_SERVER_API_AUTH_STRING=",
        ),
        valid.read_text(encoding="utf-8") + "not an assignment\n",
    ):
        invalid = tmp_path / "invalid.env"
        invalid.write_bytes(invalid_lines.encode("utf-8"))
        result = subprocess.run(
            [os.environ["BOGDA_BASH"], str(validator), str(invalid)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert "matched-secret" not in result.stdout + result.stderr
        assert "different-secret" not in result.stdout + result.stderr


def test_rollback_validates_inventory_before_state_changes() -> None:
    source = ROLLBACK.read_text(encoding="utf-8")

    assert "validate_inventory()" in source
    assert "apply_inventory()" in source
    assert source.index("\nvalidate_inventory\n") < source.index("systemctl disable --now")
    assert source.index("systemctl disable --now") < source.index("\napply_inventory\n")
    assert '[ -L "$target" ]' in source
    assert '[ -L "$backup_file" ] || [ ! -f "$backup_file" ]' in source
    assert "backup_parent=" in source
