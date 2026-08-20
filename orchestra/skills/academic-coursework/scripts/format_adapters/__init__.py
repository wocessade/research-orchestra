"""
Format adapter interface and registry.

Every adapter implements one method::

    def parse(source_path: str) -> dict:
        '''Return a partial format template dict.

        Keys extracted from the source get ``status: confirmed``;
        missing keys should be omitted so ``merge_template`` fills defaults.
        '''

Adapters are discovered via the ``ADAPTERS`` dict below.
"""

ADAPTERS: dict[str, tuple[str, str]] = {
    "docx": (
        "论文 DOCX（从学长论文中提取格式）",
        ".docx_adapter",
    ),
    "spec": (
        "规范文档（暂未实现）",
        ".spec_adapter",
    ),
}


def run_adapter(adapter_key: str, source_path: str) -> dict:
    """Dynamically import and run the named adapter.

    Adapters are loaded via absolute import (``scripts/format_adapters/`` is
    on ``sys.path``, so ``format_adapters.docx_adapter`` resolves correctly).
    """
    from importlib import import_module

    if adapter_key not in ADAPTERS:
        raise ValueError(
            f"Unknown adapter '{adapter_key}'; known: {list(ADAPTERS)}"
        )

    _, rel_module = ADAPTERS[adapter_key]
    # Convert ".docx_adapter" → "format_adapters.docx_adapter"
    abs_module = f"format_adapters{rel_module}"
    mod = import_module(abs_module)
    return mod.parse(source_path)
