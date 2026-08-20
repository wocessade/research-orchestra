#!/usr/bin/env python3
"""
Add TOC + partial-read hints to >10KB .md reference files in all 3 academic skill modules.
Run: python add_toc.py [--dry-run]
"""

import sys, os, re
from pathlib import Path

SKILLS = [
    "academic-coursework",
    "academic-journal",
    "academic-thesis",
]
BASE = Path(__file__).resolve().parent.parent.parent
SIZE_THRESHOLD = 10 * 1024  # 10KB
SKIP_PATTERNS = [r'strategists[\\/]', r'static[\\/]core[\\/]', r'SKILL\.md$', r'manifest\.yaml$']

def should_skip(path_str):
    return any(re.search(p, path_str) for p in SKIP_PATTERNS)

def has_toc(content):
    return 'prefer on-demand partial reads' in content[:500] or 'partial-read' in content[:500]

def extract_headings(content):
    """Extract ## and ### headings."""
    headings = []
    for line in content.split('\n'):
        m = re.match(r'^(#{2,3})\s+(.+)$', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if len(text) > 60:
                text = text[:57] + '...'
            headings.append((level, text))
    return headings

def build_toc_block(filepath, size_kb, headings):
    """Build a compact TOC header block."""
    sections = []
    for level, text in headings:
        marker = '#' * level
        sections.append(f"`{marker} {text}`")

    # Group in chunks of ~5 for readability
    lines = ["> **~{0} KB reference file.** Prefer on-demand partial reads. Use section headings below to jump directly.".format(size_kb)]
    if sections:
        line = "> **Sections:** " + " · ".join(sections)
        # Break long lines
        if len(line) > 200:
            # Split into multiple lines
            mid = len(sections) // 2
            line1 = "> **Sections:** " + " · ".join(sections[:mid])
            line2 = "> " + " · ".join(sections[mid:])
            lines = ["> **~{0} KB reference file.** Prefer on-demand partial reads.".format(size_kb), line1, line2]
        else:
            lines = ["> **~{0} KB reference file.** Prefer on-demand partial reads.", line]

    lines.append("")
    return "\n".join(lines)

def process_file(filepath, dry_run=False):
    content = filepath.read_text(encoding="utf-8")
    if has_toc(content):
        return False  # Already has TOC

    size_kb = round(filepath.stat().st_size / 1024)
    headings = extract_headings(content)
    if not headings:
        return False  # No headings to index

    toc_block = build_toc_block(filepath, size_kb, headings)

    # Insert after any leading header lines (version, scope, etc.) but before content
    lines = content.split('\n')
    insert_at = 0
    for i, line in enumerate(lines):
        # Skip blank lines, existing comment blocks, and metadata lines
        if line.strip() == '' or line.startswith('<!--') or line.startswith('> **~'):
            insert_at = i + 1
            continue
        if re.match(r'^# .+', line):  # Title line
            # Insert after the title and any metadata lines
            insert_at = i + 1
            # Keep going through metadata lines
            for j in range(i + 1, len(lines)):
                if lines[j].strip().startswith('## ') or lines[j].strip().startswith('> '):
                    insert_at = j + 1
                    continue
                elif lines[j].strip() == '' or lines[j].strip() == '---':
                    insert_at = j + 1
                    continue
                elif lines[j].startswith('<!--'):
                    insert_at = j + 1
                    continue
                else:
                    break
            break

    new_lines = lines[:insert_at] + [toc_block] + lines[insert_at:]
    new_content = '\n'.join(new_lines)

    if dry_run:
        print(f"  [DRY] Would add TOC to: {filepath.relative_to(BASE)}")
        return True

    filepath.write_text(new_content, encoding="utf-8")
    print(f"  [OK] Added TOC: {filepath.relative_to(BASE)} ({size_kb}KB, {len(headings)} sections)")
    return True

def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("DRY RUN — no files will be modified\n")

    total = 0
    for skill in SKILLS:
        skill_dir = BASE / skill
        if not skill_dir.exists():
            continue
        print(f"\n--- {skill} ---")
        for md_file in sorted(skill_dir.rglob("*.md")):
            path_str = str(md_file.relative_to(BASE))
            if should_skip(path_str):
                continue
            if md_file.stat().st_size < SIZE_THRESHOLD:
                continue
            if process_file(md_file, dry_run=dry_run):
                total += 1

    print(f"\n{'Would add' if dry_run else 'Added'} TOC to {total} files.")

if __name__ == "__main__":
    main()
