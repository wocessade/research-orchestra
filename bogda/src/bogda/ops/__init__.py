"""Operational helpers for the Bogda deployment bundle.

Public helpers are loaded on first access so ``python -m bogda.ops.*`` does
not import its target module before :mod:`runpy` executes it.
"""

from importlib import import_module

_SNAPSHOT_EXPORTS = (
    "create_snapshot",
    "integrity_check",
    "prune_snapshots",
    "sha256_file",
    "verify_snapshot",
)
_HEALTH_EXPORTS = (
    "DEFAULT_UNITS",
    "append_sample",
    "disk_free_bytes",
    "nearest_rank_p95",
    "parse_meminfo",
    "parse_vmstat",
    "probe_api",
    "sample_health",
    "summarize_samples",
    "unit_states",
    "wait_for_api",
)

__all__ = [*_SNAPSHOT_EXPORTS, *_HEALTH_EXPORTS]

_EXPORT_MODULES = {
    **{name: "snapshot" for name in _SNAPSHOT_EXPORTS},
    **{name: "health" for name in _HEALTH_EXPORTS},
}


def __getattr__(name: str) -> object:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value
