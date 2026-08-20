"""
Format adapter interface and registry.

Actual adapter modules live in academic-shared/scripts/format_adapters/.
This wrapper loads them via file path.
"""

import os, sys
from importlib import util

_SHARED = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..',
    'academic-shared', 'scripts', 'format_adapters'
))

ADAPTERS: dict[str, tuple[str, str]] = {
    "docx": ("论文 DOCX（从学长论文中提取格式）", "docx_adapter"),
    "spec": ("规范文档（暂未实现）", "spec_adapter"),
}


def _load_adapter_module(module_name: str):
    """Import a Python file from academic-shared by absolute path."""
    filepath = os.path.join(_SHARED, f"{module_name}.py")
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"Adapter module not found at {filepath}"
        )
    spec = util.spec_from_file_location(module_name, filepath)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_adapter(adapter_key: str, source_path: str) -> dict:
    """Load the named adapter from academic-shared and run parse()."""
    if adapter_key not in ADAPTERS:
        raise ValueError(
            f"Unknown adapter '{adapter_key}'; known: {list(ADAPTERS)}"
        )

    _, module_name = ADAPTERS[adapter_key]
    mod = _load_adapter_module(module_name)
    return mod.parse(source_path)
