from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bogda.ops.bundle import load_manifest, main, render_dry_run, validate_bundle


EXPECTED_UNITS = {
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
}
EXPECTED_ENV_LINES = (
    "PREFECT_HOME=/mnt/nas/.bogda/prefect",
    "PREFECT_API_URL=http://127.0.0.1:4200/api",
    "PREFECT_SERVER_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT",
    "PREFECT_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT",
)


@pytest.fixture
def bundle_copy(tmp_path: Path) -> Path:
    source = Path(__file__).parents[2] / "deploy" / "pi"
    destination = tmp_path / "pi"
    shutil.copytree(source, destination)
    return destination


def test_clean_bundle_has_fixed_contract(bundle_copy: Path) -> None:
    manifest = load_manifest(bundle_copy / "manifest.toml")

    assert manifest.data_root == "/mnt/nas/.bogda"
    assert manifest.worker_limit == 1
    assert set(manifest.units) == EXPECTED_UNITS
    assert validate_bundle(bundle_copy) == ()


@pytest.mark.parametrize(
    ("mutation", "replacement"),
    [
        ("data_root", 'data_root = "/mnt/broker"'),
        ("worker_limit", "worker_limit = 2"),
    ],
)
def test_manifest_contract_mutations_are_reported(
    bundle_copy: Path, mutation: str, replacement: str
) -> None:
    manifest_path = bundle_copy / "manifest.toml"
    original = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        original.replace(
            next(line for line in original.splitlines() if line.startswith(f"{mutation} =")),
            replacement,
        ),
        encoding="utf-8",
    )

    assert validate_bundle(bundle_copy)


def test_missing_unit_is_reported(bundle_copy: Path) -> None:
    (bundle_copy / "systemd" / "bogda-shadow-health.timer").unlink()

    assert validate_bundle(bundle_copy)


def test_non_bogda_unit_is_reported(bundle_copy: Path) -> None:
    manifest_path = bundle_copy / "manifest.toml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            '  "bogda-shadow-health.timer",', '  "other.service",'
        ),
        encoding="utf-8",
    )

    assert validate_bundle(bundle_copy)


@pytest.mark.parametrize("unit_name", ["worker.service", "bogda-extra.service"])
def test_unexpected_unit_asset_is_reported(bundle_copy: Path, unit_name: str) -> None:
    (bundle_copy / "systemd" / unit_name).write_text("[Service]\n", encoding="utf-8")

    assert validate_bundle(bundle_copy)


def test_real_looking_auth_value_is_reported(bundle_copy: Path) -> None:
    env_path = bundle_copy / "bogda.env.example"
    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "SET_ON_PI_NOT_IN_GIT", "admin:real-looking-token", 1
        ),
        encoding="utf-8",
    )

    assert validate_bundle(bundle_copy)


@pytest.mark.parametrize(
    ("name", "env_lines"),
    [
        ("wrong prefect home", ("PREFECT_HOME=/mnt/nas/.bogda/wrong", "PREFECT_API_URL=http://127.0.0.1:4200/api", "PREFECT_SERVER_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT", "PREFECT_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT")),
        ("wrong API URL", ("PREFECT_HOME=/mnt/nas/.bogda/prefect", "PREFECT_API_URL=http://127.0.0.1:9999/api", "PREFECT_SERVER_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT", "PREFECT_API_AUTH_STRING=SET_ON_PI_NOT_IN_GIT")),
        ("missing required key", EXPECTED_ENV_LINES[:-1]),
        ("duplicate key", (*EXPECTED_ENV_LINES, "PREFECT_HOME=/mnt/nas/.bogda/prefect")),
        ("extra key", (*EXPECTED_ENV_LINES, "UNRELATED_FLAG=true")),
        ("malformed line", (*EXPECTED_ENV_LINES, "not an assignment")),
        ("non-sentinel auth duplicate", (*EXPECTED_ENV_LINES, "PREFECT_SERVER_API_AUTH_STRING=Basic c2VjcmV0")),
    ],
)
def test_env_example_contract_mutations_are_reported(
    bundle_copy: Path, name: str, env_lines: tuple[str, ...]
) -> None:
    (bundle_copy / "bogda.env.example").write_text(
        "\n".join(env_lines) + "\n", encoding="utf-8"
    )

    assert validate_bundle(bundle_copy), name


@pytest.mark.parametrize("forbidden_reference", ["/mnt/broker", "orchestra-legacy"])
def test_forbidden_references_anywhere_in_bundle_are_reported(
    bundle_copy: Path, forbidden_reference: str
) -> None:
    (bundle_copy / "deployment-notes.txt").write_text(
        forbidden_reference, encoding="utf-8"
    )

    assert validate_bundle(bundle_copy)


def test_required_unit_fragment_is_reported(bundle_copy: Path) -> None:
    worker_path = bundle_copy / "systemd" / "bogda-pi-worker.service"
    worker_path.write_text(
        worker_path.read_text(encoding="utf-8").replace(
            "--limit 1", "--limit 2"
        ),
        encoding="utf-8",
    )

    assert validate_bundle(bundle_copy)


@pytest.mark.parametrize(
    ("unit_name", "fragment"),
    [
        (unit_name, fragment)
        for unit_name in (
            "bogda-prefect-server.service",
            "bogda-pi-worker.service",
            "bogda-prefect-snapshot.service",
            "bogda-shadow-health.service",
        )
        for fragment in (
            "ConditionPathIsMountPoint=/mnt/nas",
            "ExecCondition=/bin/sh -c 'test \"$(/usr/bin/findmnt -no FSTYPE /mnt/nas)\" = \"ext4\"'",
            "RestartSec=10s",
            "StartLimitIntervalSec=5min",
            "StartLimitBurst=5",
        )
    ],
)
def test_validator_requires_runtime_mount_ext4_and_restart_guards(
    bundle_copy: Path, unit_name: str, fragment: str
) -> None:
    """Removing any runtime guard must make the public validator reject a unit."""
    unit_path = bundle_copy / "systemd" / unit_name
    unit_path.write_text(
        unit_path.read_text(encoding="utf-8").replace(fragment, ""), encoding="utf-8"
    )

    assert f"{unit_name} missing required fragment: {fragment}" in validate_bundle(bundle_copy)


@pytest.mark.parametrize(
    "unit_name",
    ["bogda-prefect-server.service", "bogda-pi-worker.service"],
)
@pytest.mark.parametrize(
    "fragment",
    ["BindsTo=mnt-nas.mount", "After=mnt-nas.mount", "WantedBy=mnt-nas.mount"],
)
def test_runtime_services_rebind_when_nas_mount_returns(
    bundle_copy: Path, unit_name: str, fragment: str
) -> None:
    unit_path = bundle_copy / "systemd" / unit_name
    unit_path.write_text(
        unit_path.read_text(encoding="utf-8").replace(fragment, ""), encoding="utf-8"
    )

    assert f"{unit_name} missing required fragment: {fragment}" in validate_bundle(bundle_copy)


def test_install_refreshes_mount_enablement_only_for_already_enabled_services() -> None:
    install_script = Path(__file__).parents[2] / "deploy" / "pi" / "install.sh"
    source = install_script.read_text(encoding="utf-8")
    reload_at = source.index("systemctl daemon-reload")
    enabled_check = source.index('systemctl is-enabled --quiet "$unit_name"', reload_at)
    reenable = source.index('systemctl reenable "$unit_name"', enabled_check)
    start_block = source.index('if [ "$start" = true ]; then', reenable)

    assert reload_at < enabled_check < reenable < start_block


@pytest.mark.parametrize(
    "manifest_text",
    [
        'service_user = "bogda"\nunits = [',
        'service_group = "bogda"\n',
        'service_user = "bogda"\nworker_limit = "one"\n',
    ],
)
def test_invalid_manifest_raises_value_error(
    bundle_copy: Path, manifest_text: str
) -> None:
    manifest_path = bundle_copy / "manifest.toml"
    manifest_path.write_text(manifest_text, encoding="utf-8")

    with pytest.raises(ValueError):
        load_manifest(manifest_path)


def test_dry_run_is_read_only(bundle_copy: Path) -> None:
    before = {
        path.relative_to(bundle_copy): path.read_bytes()
        for path in bundle_copy.rglob("*")
        if path.is_file()
    }

    lines = render_dry_run(bundle_copy)

    after = {
        path.relative_to(bundle_copy): path.read_bytes()
        for path in bundle_copy.rglob("*")
        if path.is_file()
    }
    assert lines
    assert all(line.startswith(("CHECK ", "INSTALL ", "PRESERVE ")) for line in lines)
    assert after == before


def test_dry_run_rejects_invalid_bundle_and_describes_preserved_runtime_env(
    bundle_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = bundle_copy / "manifest.toml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace("worker_limit = 1", "worker_limit = 2"),
        encoding="utf-8",
    )

    assert main(["dry-run", str(bundle_copy)]) == 1
    assert "CHECK manifest worker_limit must be 1" in capsys.readouterr().out

    lines = render_dry_run(Path(__file__).parents[2] / "deploy" / "pi")
    assert "PRESERVE existing runtime env /etc/bogda/bogda.env" in lines
    assert "INSTALL example env only when /etc/bogda/bogda.env is absent" in lines
