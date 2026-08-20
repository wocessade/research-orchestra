#!/usr/bin/env python3
"""
DOCX → segmented MD file tree + _structure.json

Usage:
    python docx_segmenter.py <input.docx> <output_dir>
"""

import sys, os, re, json
from docx import Document

# ── heading detection (content-based, since all Normal style) ──────────

# Journal article patterns (default)
H1_RE   = re.compile(r'^([1-9])\s+\S')                  # "1 引言", "4 结论"
H2_RE   = re.compile(r'^([1-9]\.[0-9]+)\s+\S')          # "2.1 实验材料"
H3_RE   = re.compile(r'^([1-9]\.[0-9]+\.[0-9]+)\s+\S')  # "3.1.1 丝素蛋白"

# Thesis-specific patterns (activated via --mode thesis)
TH1_CHN    = re.compile(r'^第[一二三四五六七八九十\d]+章\s+\S')  # "第一章 绪论"
TH1_NAMED  = re.compile(r'^(摘\s*要|致\s*谢|参考文献|附\s*录|Abstract)$')
# NOTE: "摘要" / "致谢" 等整段就是标题，无后续内容，前后中文均需空格

_mode = 'journal'  # 'journal' | 'thesis'

def set_mode(mode: str):
    global _mode
    _mode = mode

def detect_heading_level(text: str) -> int | None:
    """Return heading level (1-3) or None for plain paragraph."""
    t = text.strip()
    if H1_RE.match(t): return 1
    if _mode == 'thesis':
        if TH1_CHN.match(t): return 1
        if TH1_NAMED.match(t): return 1
    if H2_RE.match(t): return 2
    if H3_RE.match(t): return 3
    return None


def sanitize(segment: str, max_len: int = 40) -> str:
    """Turn heading text into a safe directory/file name."""
    s = segment.strip().lower()
    s = re.sub(r'[^\w一-鿿\-]+', '_', s)
    s = s.strip('_')
    s = s[:max_len].rstrip('_')
    return s or 'untitled'


# ── figure / table detection ──────────────────────────────────────────

# Matches "图3 (b)", "图5：...", "图2(a)", "图4 (a)" etc
FIG_CAP_RE = re.compile(r'^图\d+(\s*\(?[a-zA-Z]\)?)?[.：:、\s（(]')
TAB_CAP_RE = re.compile(r'^表\d+[.：:、\s]')
FIG_REF_RE = re.compile(r'图(\d+)')
TAB_REF_RE = re.compile(r'表(\d+)')


def detect_figure_refs(text: str) -> list[tuple[int, int, str]]:
    """Return list of (fig_number, start_pos, matched_text)."""
    results = []
    for m in FIG_REF_RE.finditer(text):
        results.append((int(m.group(1)), m.start(), m.group()))
    return results


# ── main segmenter ────────────────────────────────────────────────────

def segment_docx(docx_path: str, output_dir: str, mode: str = 'journal') -> dict:
    """
    Unpack a DOCX into:
      {output_dir}/
        _structure.json
        front/            (title, abstract — pre-section content)
        N_section_title/  (one dir per level-1 heading)
          N.N_subsection/
            P{index}.md   (one file per paragraph)
    Returns the _structure dict.
    """
    global _mode
    _mode = mode
    doc = Document(docx_path)
    paragraphs = list(doc.paragraphs)

    section_tree = []          # list of section nodes
    figures = []
    tables = []
    modified_sections = []

    current_l1 = None          # {path, heading, paras[]}
    current_l2 = None          # {path, heading, paras[]}
    current_l3 = None

    for idx, p in enumerate(paragraphs):
        text = (p.text or '').strip()
        level = detect_heading_level(text)

        # ── close previous leaf ──
        if level is not None:
            # flush current l3
            if current_l3 is not None:
                if current_l2 is not None:
                    current_l2.setdefault('children', []).append(current_l3)
                elif current_l1 is not None:
                    current_l1.setdefault('children', []).append(current_l3)
                current_l3 = None
            # flush current l2
            if level <= 2 and current_l2 is not None:
                if current_l1 is not None:
                    current_l1.setdefault('children', []).append(current_l2)
                current_l2 = None
            # flush current l1
            if level == 1 and current_l1 is not None:
                section_tree.append(current_l1)
                current_l1 = None

            heading_text = text
            slug = sanitize(heading_text)
            node = {'heading': heading_text, 'paragraphs': [], 'text': text, 'heading_idx': idx}

            if level == 1:
                node['path'] = f'{idx:04d}_{slug}'
                current_l1 = node
            elif level == 2:
                node['path'] = f'{idx:04d}_{slug}'
                current_l2 = node
            elif level == 3:
                node['path'] = f'{idx:04d}_{slug}'
                current_l3 = node
        else:
            # Ordinary paragraph — attach to current container
            if current_l3 is not None:
                current_l3['paragraphs'].append(idx)
            elif current_l2 is not None:
                current_l2['paragraphs'].append(idx)
            elif current_l1 is not None:
                current_l1['paragraphs'].append(idx)

        # ── figure / table detection ──
        if FIG_CAP_RE.match(text):
            m = FIG_REF_RE.search(text)
            num = int(m.group(1)) if m else len(figures) + 1
            figures.append({
                'number': num,
                'caption': text,
                'paragraph_index': idx,
                'cross_refs': []
            })

        if TAB_CAP_RE.match(text):
            m = TAB_REF_RE.search(text)
            num = int(m.group(1)) if m else len(tables) + 1
            tables.append({
                'number': num,
                'caption': text,
                'paragraph_index': idx,
            })

    # Close final containers
    if current_l3 is not None:
        (current_l2 or current_l1).setdefault('children', []).append(current_l3)
    if current_l2 is not None:
        if current_l1 is not None:
            current_l1.setdefault('children', []).append(current_l2)
    if current_l1 is not None:
        section_tree.append(current_l1)

    # ── write MD files ────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)

    def write_paragraph_md(dir_path, p_idx, text, is_new=False):
        os.makedirs(dir_path, exist_ok=True)
        prefix = 'P_new_' if is_new else 'P'
        fname = f'{prefix}{p_idx:04d}.md'
        fpath = os.path.join(dir_path, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        return fname

    # Front matter (paragraphs before first heading)
    first_heading_idx = None
    if section_tree:
        first_heading_idx = section_tree[0].get('heading_idx')

    front_dir = os.path.join(output_dir, 'front')
    for idx, p in enumerate(paragraphs):
        if first_heading_idx is not None and idx >= first_heading_idx:
            break
        text = (p.text or '').strip()
        if text:
            write_paragraph_md(front_dir, idx, text)

    # Sections
    def write_section(node, parent_dir):
        heading_text = node.get('text', '')
        slug = sanitize(node['heading'], 40)
        dir_path = os.path.join(parent_dir, f'{slug}')
        os.makedirs(dir_path, exist_ok=True)

        # Write heading paragraph
        heading_idx = node.get('heading_idx')
        if heading_idx is not None:
            write_paragraph_md(dir_path, heading_idx, heading_text)

        # Write content paragraphs
        for p_idx in node.get('paragraphs', []):
            text = (paragraphs[p_idx].text or '').strip()
            if text:
                write_paragraph_md(dir_path, p_idx, text)

        # Store relative path
        rel = os.path.relpath(dir_path, output_dir)
        node['path'] = rel.replace('\\', '/')

        # Recurse into children
        for child in node.get('children', []):
            write_section(child, dir_path)

    for l1_node in section_tree:
        write_section(l1_node, output_dir)

    # ── cross-reference scan ──
    for fig in figures:
        pi = fig['paragraph_index']
        refs = []
        for idx, p in enumerate(paragraphs):
            text = p.text or ''
            for num, pos, mtext in detect_figure_refs(text):
                if num == fig['number']:
                    refs.append({'paragraph_index': idx, 'text_snippet': mtext})
        fig['cross_refs'] = refs[:20]  # cap

    # ── write _structure.json ──
    structure = {
        'sections': section_tree,
        'figures': figures,
        'tables': tables,
        'modified_sections': modified_sections,
    }
    with open(os.path.join(output_dir, '_structure.json'), 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    return structure


# ── figure helpers (operate on structure dict) ────────────────────────

def build_figure_inventory(paragraphs) -> list[dict]:
    """Standalone: re-extract figure inventory from paragraph list."""
    figures = []
    for idx, p in enumerate(paragraphs):
        text = (p.text or '').strip()
        if FIG_CAP_RE.match(text):
            m = FIG_REF_RE.search(text)
            num = int(m.group(1)) if m else len(figures) + 1
            figures.append({
                'number': num,
                'caption': text,
                'paragraph_index': idx,
                'cross_refs': []
            })
    return figures


def renumber_figures(figures: list[dict]) -> list[dict]:
    """Renumber figures sequentially by paragraph position."""
    figures.sort(key=lambda f: f['paragraph_index'])
    for new_n, fig in enumerate(figures, 1):
        old_n = fig['number']
        fig['number'] = new_n
        # Update caption text
        fig['caption'] = fig['caption'].replace(f'图{old_n}', f'图{new_n}', 1)
        # Update cross-refs
        for ref in fig.get('cross_refs', []):
            ref['text_snippet'] = ref['text_snippet'].replace(f'图{old_n}', f'图{new_n}')
    return figures


def validate_figures(figures: list[dict]) -> list[str]:
    """Return list of issues found."""
    issues = []
    numbers = [f['number'] for f in figures]
    captions = [f['caption'] for f in figures]

    # Check sequence
    expected = list(range(1, len(figures) + 1))
    if numbers != expected:
        issues.append(f'Figure numbering not sequential: got {numbers}, expected {expected}')

    # Check duplicates
    if len(set(captions)) != len(captions):
        seen = set()
        for c in captions:
            if c in seen:
                issues.append(f'Duplicate figure caption: {c[:50]}')
            seen.add(c)

    # Check order vs paragraph position
    positions = [f['paragraph_index'] for f in figures]
    if positions != sorted(positions):
        issues.append('Figure order does not match paragraph order')
        # Show specifics
        for i in range(1, len(positions)):
            if positions[i] < positions[i - 1]:
                issues.append(
                    f'  图{figures[i-1]["number"]}(P{positions[i-1]}) '
                    f'before 图{figures[i]["number"]}(P{positions[i]})'
                )

    # Orphaned cross-refs (figure mentioned but no caption)
    # (This requires the full paragraph scan — done in validate_figures_from_docx)
    return issues


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    docx_path = sys.argv[1]
    output_dir = sys.argv[2]

    mode = 'journal'
    if '--mode' in sys.argv:
        idx = sys.argv.index('--mode')
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]

    if not os.path.isfile(docx_path):
        print(f'Error: input file not found: {docx_path}')
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    structure = segment_docx(docx_path, output_dir, mode=mode)

    sections_count = len(structure['sections'])
    figures_count = len(structure['figures'])

    print(f'Segmented {docx_path} → {output_dir}/')
    print(f'  Sections: {sections_count}')
    print(f'  Figures:  {figures_count}')
    print(f'  Tables:   {len(structure["tables"])}')


if __name__ == '__main__':
    main()
