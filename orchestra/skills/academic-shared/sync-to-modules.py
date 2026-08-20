#!/usr/bin/env python3
"""
同步 academic-shared/ 中的 canonical 文件到各模块的本地副本。

用法:
    python sync-to-modules.py --component skills-embedded
    python sync-to-modules.py --component literature
    python sync-to-modules.py --component static-core
    python sync-to-modules.py --component evaluate
    python sync-to-modules.py --all

组件与目标模块的映射:
    skills-embedded → journal/ (完整39文件), thesis/ (子集13), coursework/ (子集7)
    literature       → journal/, thesis/, coursework/ (路由到 shared，仅用于维护)
    static-core      → journal/, thesis/, coursework/ (5 canonical 核心文件)
    evaluate         → journal/, thesis/ (coursework 使用 auto_checks，不包含)
"""

import sys
import os
import shutil
import argparse

SHARED_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.dirname(SHARED_DIR)

# 组件 → {目标模块: (源相对路径, 目标相对路径)}
COMPONENTS = {
    "skills-embedded": {
        "academic-journal": ("skills-embedded", "skills-embedded"),
        "academic-thesis": ("skills-embedded", "skills-embedded"),
        "academic-coursework": ("skills-embedded", "skills-embedded"),
    },
    "literature": {
        "academic-journal": ("literature", "literature"),
        "academic-thesis": ("literature", "literature"),
        "academic-coursework": ("literature", "literature"),
    },
    "static-core": {
        "academic-journal": ("static-core", "static/core"),
        "academic-thesis": ("static-core", "static/core"),
        "academic-coursework": ("static-core", "static/core"),
    },
    "evaluate": {
        "academic-journal": ("evaluate", "evaluate"),
        "academic-thesis": ("evaluate", "evaluate"),
    },
}

# Per-module file allow-lists: 只同步列出的文件，None = 同步全部
# key = component:module → list of filenames
FILE_FILTERS = {
    "skills-embedded:academic-thesis": [
        "docx.md",
        "generate-image.md",
        "hypothesis-generation.md",
        "latex-document-skill.md",
        "latex-paper-en.md",
        "latex-thesis-zh.md",
        "nature-paper2ppt.md",
        "paper-lookup.md",
        "pdf.md",
        "pptx.md",
        "scientific-brainstorming.md",
        "scientific-schematics.md",
        "scientific-slides.md",
        # 以下文件由 manifest embedded_references 声明，从 academic-shared 复制
        "scientific-visualization.md",
        "nature-figure.md",
    ],
    "skills-embedded:academic-coursework": [
        "docx.md",
        "generate-image.md",
        "latex-document-skill.md",
        "latex-paper-en.md",
        "latex-thesis-zh.md",
        "markdown-mermaid-writing.md",
        "nature-figure.md",
        "paper-lookup.md",
        "pdf.md",
        "scientific-brainstorming.md",
        "scientific-schematics.md",
        "scientific-visualization.md",
    ],
    "literature:academic-journal": [],        # 路由到 shared，本地不保留副本
    "literature:academic-thesis": [],         # 同上
    "literature:academic-coursework": [],      # 同上
    "evaluate:academic-journal": [],           # 路由到 shared，本地不保留副本
    "evaluate:academic-thesis": [],            # 同上

# Composer files (academic-shared/composers/) are NOT synced to modules.
# Module strategists reference them via relative paths in manifest.yaml.
}


def get_filter(component: str, module: str):
    """获取模块的文件过滤器，None = 不过滤（同步全部）"""
    return FILE_FILTERS.get(f"{component}:{module}")


def sync_component(component: str, dry_run: bool = False):
    """同步指定组件到所有目标模块。"""
    if component not in COMPONENTS:
        print(f"错误: 未知组件 '{component}'。支持: {', '.join(COMPONENTS.keys())}")
        sys.exit(1)

    targets = COMPONENTS[component]
    source_dir = os.path.join(SHARED_DIR, component)

    if not os.path.isdir(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)

    # 获取源文件列表
    source_files = []
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), source_dir)
            source_files.append(rel_path)

    print(f"组件 '{component}': {len(source_files)} 个文件")
    print(f"源目录: {source_dir}")

    for module, (src_rel, dst_rel) in targets.items():
        module_dir = os.path.join(SKILLS_DIR, module)
        dst_dir = os.path.join(module_dir, dst_rel)
        file_filter = get_filter(component, module)

        if not os.path.isdir(module_dir):
            print(f"  跳过 {module}: 模块目录不存在")
            continue

        os.makedirs(dst_dir, exist_ok=True)

        copied = 0
        skipped = 0
        filtered = 0
        for rel_path in source_files:
            # 文件名级别过滤（仅浅层文件，子目录文件不适用）
            basename = os.path.basename(rel_path)
            if file_filter is not None and basename not in file_filter:
                filtered += 1
                continue

            src_file = os.path.join(source_dir, rel_path)
            dst_file = os.path.join(dst_dir, rel_path)

            # 目标文件已存在且内容相同 → 跳过
            if os.path.isfile(dst_file):
                with open(src_file, "rb") as sf, open(dst_file, "rb") as df:
                    if sf.read() == df.read():
                        skipped += 1
                        continue

            dr = "[DRY RUN] " if dry_run else ""
            print(f"  {dr}{module}/{dst_rel}/{rel_path}")
            if not dry_run:
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)
            copied += 1

        print(f"  → {module}: {copied} 复制, {skipped} 已同步, {filtered} 过滤")

    actual = sum(1 for m in targets if os.path.isdir(os.path.join(SKILLS_DIR, m)))
    print(f"完成: {component} → {actual} 模块")


def main():
    parser = argparse.ArgumentParser(description="同步 academic-shared canonical 文件到模块")
    parser.add_argument("--component", "-c", help="组件名")
    parser.add_argument("--all", "-a", action="store_true", help="同步所有组件")
    parser.add_argument("--dry-run", "-n", action="store_true", help="仅预览，不实际复制")
    args = parser.parse_args()

    if not args.component and not args.all:
        parser.print_help()
        sys.exit(1)

    if args.all:
        for comp in COMPONENTS:
            sync_component(comp, dry_run=args.dry_run)
    else:
        sync_component(args.component, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
