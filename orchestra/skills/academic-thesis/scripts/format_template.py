#!/usr/bin/env python3
"""
Unified thesis format template — the single source of truth for all layout styles.

Architecture:
  source_files (docx/规范/操作文档)
       │  ┌─ adapters parse & normalize ─┐
       ▼  ▼                               ▼
    unified YAML dict  ─── assemble_thesis.py  ──→  final .docx
       ▲
       └── built-in defaults (fallback when source lacks a rule)

Every style entry carries a `status` field:
  - "confirmed": extracted from a source file authoritatively
  - "defaulted": not found in any source, using built-in default
  - "conflict":  two sources disagree; first-source value used
"""

import os
import copy
from datetime import datetime
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


# ══════════════════════════════════════════════════════════════════
# 1.  DEFAULT TEMPLATE  (all styles marked "defaulted")
# ══════════════════════════════════════════════════════════════════

_DEFAULT_TEMPLATE: dict[str, Any] = {
    "meta": {
        "generated_at": None,
        "source": "default",
    },
    "page": {
        "paper": "A4",
        "width_cm": 21.0,
        "height_cm": 29.7,
        "margins": {"top": 2.5, "bottom": 2.5, "left": 3.0, "right": 2.5},
        "header_distance": 1.5,
        "footer_distance": 1.75,
    },
    "styles": {
        "body": {
            "font_cn": "宋体",
            "font_en": "Times New Roman",
            "size": "12pt",
            "bold": False,
            "line_spacing": 1.5,
            "first_line_indent": "2ch",
            "alignment": "justify",
            "space_after": "0pt",
            "status": "defaulted",
        },
        "chapter_title": {
            "font_cn": "黑体",
            "size": "16pt",
            "bold": True,
            "alignment": "center",
            "line_spacing": 1.5,
            "space_before": "0pt",
            "space_after": "12pt",
            "status": "defaulted",
        },
        "section_h1": {
            "font_cn": "黑体",
            "size": "14pt",
            "bold": True,
            "alignment": "left",
            "line_spacing": 1.5,
            "space_before": "12pt",
            "space_after": "6pt",
            "status": "defaulted",
        },
        "section_h2": {
            "font_cn": "黑体",
            "size": "12pt",
            "bold": True,
            "alignment": "left",
            "line_spacing": 1.5,
            "space_before": "6pt",
            "space_after": "3pt",
            "status": "defaulted",
        },
        "blockquote": {
            "font_cn": "宋体",
            "size": "10.5pt",
            "line_spacing": 1.25,
            "left_indent": "1.0cm",
            "first_line_indent": "0cm",
            "status": "defaulted",
        },
        "table_number": {
            "font_cn": "黑体",
            "size": "10.5pt",
            "bold": True,
            "placement": "above",
            "alignment": "left",
            "status": "defaulted",
        },
        "table_title": {
            "font_cn": "宋体",
            "size": "10.5pt",
            "bold": False,
            "alignment": "left",
            "status": "defaulted",
        },
        "figure_number": {
            "font_cn": "黑体",
            "size": "10.5pt",
            "bold": True,
            "placement": "below",
            "alignment": "center",
            "status": "defaulted",
        },
        "figure_title": {
            "font_cn": "宋体",
            "size": "10.5pt",
            "bold": False,
            "alignment": "center",
            "status": "defaulted",
        },
        "reference": {
            "font_cn": "宋体",
            "size": "10.5pt",
            "line_spacing": 1.0,
            "alignment": "left",
            "space_after": "0pt",
            "hanging_indent": "0.74cm",
            "status": "defaulted",
        },
        "page_header": {
            "font_cn": "宋体",
            "size": "9pt",
            "alignment": "center",
            "status": "defaulted",
        },
        "page_footer": {
            "font_cn": "Times New Roman",
            "size": "9pt",
            "alignment": "center",
            "status": "defaulted",
        },
        "toc_title": {
            "font_cn": "黑体",
            "size": "16pt",
            "bold": True,
            "alignment": "center",
            "space_after": "12pt",
            "status": "defaulted",
        },
        "abstract_title": {
            "font_cn": "黑体",
            "size": "16pt",
            "bold": True,
            "alignment": "center",
            "space_after": "12pt",
            "status": "defaulted",
        },
        "declaration_title": {
            "font_cn": "黑体",
            "size": "16pt",
            "bold": True,
            "alignment": "center",
            "space_after": "12pt",
            "status": "defaulted",
        },
        "acknowledgement_title": {
            "font_cn": "黑体",
            "size": "16pt",
            "bold": True,
            "alignment": "center",
            "space_after": "12pt",
            "status": "defaulted",
        },
        "toc_entry_1": {
            "font_cn": "黑体",
            "size": "12pt",
            "bold": False,
            "line_spacing": 1.5,
            "status": "defaulted",
        },
        "toc_entry_2": {
            "font_cn": "宋体",
            "size": "12pt",
            "bold": False,
            "line_spacing": 1.5,
            "status": "defaulted",
        },
    },
    "structure": [
        {"type": "cover"},
        {"type": "page_break"},
        {"type": "chapter", "title": "摘  要", "source": "T4_中文摘要.md"},
        {"type": "page_break"},
        {"type": "chapter", "title": "Abstract", "source": "T4_英文摘要.md"},
        {"type": "page_break"},
        {"type": "toc"},
        {"type": "page_break"},
        {"type": "chapter", "title": "第1章 绪论", "source": "T4_第1章_绪论.md"},
        {"type": "chapter", "title": "第2章 文献综述", "source": "T4_第2章_文献综述.md"},
        {"type": "chapter", "title": "第3章 研究方法", "source": "T4_第3章_研究方法.md"},
        # 以下为核心章节占位符，根据实际论文替换标题和源文件名
        {"type": "chapter", "title": "第4章 核心章节一", "source": "T4_第4章_核心章节一.md"},
        {"type": "chapter", "title": "第5章 核心章节二", "source": "T4_第5章_核心章节二.md"},
        {"type": "chapter", "title": "第6章 核心章节三", "source": "T4_第6章_核心章节三.md"},
        {"type": "chapter", "title": "第7章 结论", "source": "T4_第7章_结论.md"},
        {"type": "page_break"},
        {"type": "chapter", "title": "参考文献", "source": "bibliography.md"},
        {"type": "page_break"},
        {"type": "chapter", "title": "致  谢", "source": "T4_致谢.md"},
        {"type": "page_break"},
        {"type": "declaration"},
    ],
}


# ══════════════════════════════════════════════════════════════════
# 2.  API
# ══════════════════════════════════════════════════════════════════

def build_default_template() -> dict[str, Any]:
    """Return a deep copy of the built-in default template."""
    return copy.deepcopy(_DEFAULT_TEMPLATE)


def load_template(path: str) -> dict[str, Any]:
    """Load a format template from a YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required. Run: pip install pyyaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Template file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def save_template(config: dict[str, Any], path: str) -> None:
    """Persist a format template to a YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required. Run: pip install pyyaml")
    config = copy.deepcopy(config)
    config.setdefault("meta", {})
    config["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"  [OK] Template saved: {path}")


def get_style(config: dict[str, Any], role: str) -> dict[str, Any] | None:
    """Look up a style by role name from the config dict."""
    return config.get("styles", {}).get(role)


def set_style_status(config: dict[str, Any], role: str, status: str) -> None:
    """Override the status of a single style role in-place."""
    style = config.get("styles", {}).get(role)
    if style is not None:
        style["status"] = status


def merge_template(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Merge two templates.  ``override`` wins on every key.

    For each style role:
      - present in override only         -> copied as-is
      - present in base only             -> kept as-is
      - present in both AND match        -> status = "confirmed"
      - present in both AND differ       -> override wins, status = "conflict"
    """
    base = copy.deepcopy(base)
    override = copy.deepcopy(override)

    base_styles = base.setdefault("styles", {})
    override_styles = override.get("styles", {})

    for role, override_style in override_styles.items():
        if role not in base_styles:
            base_styles[role] = override_style
            continue

        base_style = base_styles[role]
        different = False
        for key in override_style:
            if key == "status":
                continue
            if key in base_style and base_style[key] != override_style[key]:
                different = True
                base_style[key] = override_style[key]

        if different:
            base_style["status"] = "conflict"
        else:
            base_style["status"] = "confirmed"

    # Override page-level config
    base_page = base.setdefault("page", {})
    override_page = override.get("page", {})
    for key, val in override_page.items():
        if isinstance(val, dict) and isinstance(base_page.get(key), dict):
            base_page[key].update(val)
        else:
            base_page[key] = val

    return base


def generate_report(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Summarise all styles that are NOT ``confirmed``."""
    items: list[dict[str, Any]] = []
    styles = config.get("styles", {})
    for role, style in styles.items():
        st = style.get("status", "defaulted")
        if st != "confirmed":
            items.append({"role": role, "status": st, "style": style})
    return items


def print_report(report: list[dict[str, Any]]) -> None:
    """Print a human-readable summary of unconfirmed styles."""
    if not report:
        print("  [OK] All styles confirmed.\n")
        return
    for item in report:
        tag = "[DEFAULTED]" if item["status"] == "defaulted" else "[CONFLICT]"
        print(f"  {tag} {item['role']}")
        style = item["style"]
        for k, v in style.items():
            if k != "status":
                print(f"       {k}: {v}")
    print()


# ══════════════════════════════════════════════════════════════════
# 3.  CLI quick-check
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tpl = build_default_template()
    print("=== Default template ===")
    styles = tpl["styles"]
    print(f"  Styles defined: {len(styles)}")
    report = generate_report(tpl)
    print(f"  Unresolved: {len(report)}")
    print_report(report)

    test_path = os.path.join(os.path.dirname(__file__), "default_thesis_format.yaml")
    save_template(tpl, test_path)
    loaded = load_template(test_path)
    assert len(loaded["styles"]) == len(styles)
    print(f"  Round-trip OK ({len(loaded['styles'])} styles)")
