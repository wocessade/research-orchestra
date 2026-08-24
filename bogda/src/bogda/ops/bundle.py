"""Validation and dry-run rendering for the local-only Pi bundle."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import tomllib


EXPECTED_VALUES = {
    "service_user": "bogda",
    "service_group": "bogda",
    "program_root": "/opt/bogda",
    "config_root": "/etc/bogda",
    "env_file": "/etc/bogda/bogda.env",
    "data_root": "/mnt/nas/.bogda",
    "prefect_home": "/mnt/nas/.bogda/prefect",
    "database": "/mnt/nas/.bogda/prefect/prefect.db",
    "snapshot_root": "/mnt/nas/.bogda/snapshots",
    "health_root": "/mnt/nas/.bogda/manifests/health",
    "api_url": "http://127.0.0.1:4200/api",
    "work_pool": "pi-service",
}
EXPECTED_UNITS = (
    "bogda-prefect-server.service",
    "bogda-pi-worker.service",
    "bogda-prefect-snapshot.service",
    "bogda-prefect-snapshot.timer",
    "bogda-shadow-health.service",
    "bogda-shadow-health.timer",
)
REQUIRED_UNIT_FRAGMENTS = {
    "bogda-prefect-server.service": (
        "User=bogda",
        "Group=bogda",
        "EnvironmentFile=/etc/bogda/bogda.env",
        "RequiresMountsFor=/mnt/nas/.bogda",
        "Restart=on-failure",
        "ExecStart=/opt/bogda/.venv/bin/prefect server start --host 0.0.0.0 --port 4200",
    ),
    "bogda-pi-worker.service": (
        "User=bogda",
        "Group=bogda",
        "EnvironmentFile=/etc/bogda/bogda.env",
        "RequiresMountsFor=/mnt/nas/.bogda",
        "Restart=on-failure",
        "After=bogda-prefect-server.service",
        "Requires=bogda-prefect-server.service",
        "ExecStartPre=/opt/bogda/.venv/bin/python -m bogda.ops.health wait-api --url http://127.0.0.1:4200/api --timeout 60",
        "ExecStart=/opt/bogda/.venv/bin/prefect worker start --pool pi-service --type process --limit 1 --create-pool-if-not-found",
    ),
    "bogda-prefect-snapshot.service": (
        "User=bogda",
        "Group=bogda",
        "EnvironmentFile=/etc/bogda/bogda.env",
        "RequiresMountsFor=/mnt/nas/.bogda",
        "Restart=on-failure",
        "Type=oneshot",
        "ExecStart=/opt/bogda/.venv/bin/python -m bogda.ops.snapshot create --source /mnt/nas/.bogda/prefect/prefect.db --destination /mnt/nas/.bogda/snapshots --keep 7",
    ),
    "bogda-prefect-snapshot.timer": (
        "OnCalendar=daily",
        "Persistent=true",
        "Unit=bogda-prefect-snapshot.service",
    ),
    "bogda-shadow-health.service": (
        "User=bogda",
        "Group=bogda",
        "EnvironmentFile=/etc/bogda/bogda.env",
        "RequiresMountsFor=/mnt/nas/.bogda",
        "Restart=on-failure",
        "Type=oneshot",
        "ExecStart=/opt/bogda/.venv/bin/python -m bogda.ops.health sample --output /mnt/nas/.bogda/manifests/health/samples.jsonl",
    ),
    "bogda-shadow-health.timer": (
        "OnBootSec=5min",
        "OnUnitActiveSec=5min",
        "Persistent=true",
        "Unit=bogda-shadow-health.service",
    ),
}
REQUIRED_KEYS = (*EXPECTED_VALUES, "worker_limit", "units")
AUTH_SENTINEL = "SET_ON_PI_NOT_IN_GIT"


@dataclass(frozen=True)
class BundleManifest:
    service_user: str
    service_group: str
    program_root: str
    config_root: str
    env_file: str
    data_root: str
    prefect_home: str
    database: str
    snapshot_root: str
    health_root: str
    api_url: str
    work_pool: str
    worker_limit: int
    units: tuple[str, ...]


def load_manifest(path: Path) -> BundleManifest:
    """Load a structurally valid deployment manifest from *path*."""
    try:
        with path.open("rb") as manifest_file:
            data = tomllib.load(manifest_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"invalid manifest: {path}") from error

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"manifest missing keys: {', '.join(missing)}")
    if any(not isinstance(data[key], str) for key in EXPECTED_VALUES):
        raise ValueError("manifest string fields must be strings")
    if not isinstance(data["worker_limit"], int) or isinstance(data["worker_limit"], bool):
        raise ValueError("manifest worker_limit must be an integer")
    if not isinstance(data["units"], list) or any(
        not isinstance(unit, str) for unit in data["units"]
    ):
        raise ValueError("manifest units must be a list of strings")

    return BundleManifest(
        **{key: data[key] for key in EXPECTED_VALUES},
        worker_limit=data["worker_limit"],
        units=tuple(data["units"]),
    )


def validate_bundle(bundle_root: Path) -> tuple[str, ...]:
    """Return all deployment-contract violations without changing *bundle_root*."""
    manifest = load_manifest(bundle_root / "manifest.toml")
    violations: list[str] = []

    for field, expected in EXPECTED_VALUES.items():
        if getattr(manifest, field) != expected:
            violations.append(f"manifest {field} must be {expected!r}")
    if manifest.worker_limit != 1:
        violations.append("manifest worker_limit must be 1")
    if set(manifest.units) != set(EXPECTED_UNITS) or len(manifest.units) != len(EXPECTED_UNITS):
        violations.append("manifest units must be the fixed Pi unit inventory")
    for unit in manifest.units:
        if not unit.startswith("bogda-"):
            violations.append(f"unit filename must start with bogda-: {unit}")

    systemd_directory = bundle_root / "systemd"
    actual_units = {
        path.name
        for path in systemd_directory.iterdir()
        if path.is_file() and path.suffix in {".service", ".timer"}
    } if systemd_directory.is_dir() else set()
    if actual_units != set(EXPECTED_UNITS):
        violations.append("systemd units must be the fixed Pi unit inventory")
    for unit in actual_units:
        if not unit.startswith("bogda-"):
            violations.append(f"unit filename must start with bogda-: {unit}")

    expected_deployable_files = [
        bundle_root / "manifest.toml",
        bundle_root / "bogda.env.example",
        *(bundle_root / "systemd" / unit for unit in EXPECTED_UNITS),
    ]
    for asset in expected_deployable_files:
        if not asset.is_file():
            violations.append(f"missing deployment asset: {asset.relative_to(bundle_root)}")
    for asset in (path for path in bundle_root.rglob("*") if path.is_file()):
        content = asset.read_text(encoding="utf-8")
        if "/mnt/broker" in content:
            violations.append(f"deprecated /mnt/broker reference: {asset.relative_to(bundle_root)}")
        if "orchestra-" in content.lower():
            violations.append(f"Orchestra reference: {asset.relative_to(bundle_root)}")

    env_path = bundle_root / "bogda.env.example"
    if env_path.is_file():
        env_lines = set(env_path.read_text(encoding="utf-8").splitlines())
        for variable in ("PREFECT_SERVER_API_AUTH_STRING", "PREFECT_API_AUTH_STRING"):
            required = f"{variable}={AUTH_SENTINEL}"
            if required not in env_lines:
                violations.append(f"{variable} must use the non-secret sentinel")

    for unit, fragments in REQUIRED_UNIT_FRAGMENTS.items():
        unit_path = bundle_root / "systemd" / unit
        if not unit_path.is_file():
            continue
        content = unit_path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in content:
                violations.append(f"{unit} missing required fragment: {fragment}")

    return tuple(violations)


def render_dry_run(bundle_root: Path) -> tuple[str, ...]:
    """Describe a non-mutating installation of a valid Pi bundle."""
    manifest = load_manifest(bundle_root / "manifest.toml")
    violations = validate_bundle(bundle_root)
    validation = "valid" if not violations else f"failed ({len(violations)} violations)"
    lines = [
        f"CHECK manifest validation: {validation}",
        f"INSTALL service account {manifest.service_user}:{manifest.service_group}",
        f"INSTALL target directory {manifest.program_root}",
        f"INSTALL target directory {manifest.config_root}",
        f"INSTALL target directory {manifest.snapshot_root}",
        f"INSTALL target directory {manifest.health_root}",
        f"INSTALL env {bundle_root / 'bogda.env.example'} -> {manifest.env_file}",
    ]
    lines.extend(
        f"INSTALL unit {bundle_root / 'systemd' / unit} -> /etc/systemd/system/{unit}"
        for unit in manifest.units
    )
    lines.extend(
        (
            "INSTALL systemd daemon reload",
            f"PRESERVE data root {manifest.data_root}",
            "PRESERVE no service starts unless --start is supplied later",
        )
    )
    return tuple(lines)


def main(arguments: list[str] | None = None) -> int:
    """Run the bundle validator command-line interface."""
    parser = argparse.ArgumentParser(prog="python -m bogda.ops.bundle")
    parser.add_argument("command", choices=("check", "dry-run"))
    parser.add_argument("bundle_root", type=Path)
    args = parser.parse_args(arguments)

    try:
        if args.command == "dry-run":
            for line in render_dry_run(args.bundle_root):
                print(line)
            return 0

        violations = validate_bundle(args.bundle_root)
    except ValueError as error:
        print(f"CHECK {error}")
        return 1

    if violations:
        for violation in violations:
            print(f"CHECK {violation}")
        return 1
    print("CHECK bundle valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
