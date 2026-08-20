#!/usr/bin/env python3
"""
Assemble segmented MD + unpacked DOCX → revised DOCX.

Usage:
    python docx_assembler.py <unpacked_dir> <segments_dir> <output.docx>

Phases:
  1. Update existing paragraphs (P\d{4}.md → update w:t in document.xml)
  2. Insert new paragraphs (P_new_\d+.md → clone w:pPr from preceding para)
  3. Apply figure renumbering (update "图N" cross-references)
  4. Repack the DOCX

Assembly principle:
  - Walk segments/ in file order (= document order from segmenter)
  - Old paragraphs: update text in-place (preserve w:p, w:rPr, etc.)
  - New paragraphs: clone preceding para's w:pPr, create fresh w:p with text
"""

import sys, os, re, json, subprocess
from collections import defaultdict
from copy import deepcopy
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# Path to docx skill scripts (unpack.py / pack.py)
_DOCX_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', '..',
    'plugins', 'cache', 'anthropic-agent-skills',
    'example-skills', '575462609294',
    'skills', 'docx', 'scripts', 'office'
))
UNPACK_PY = os.path.join(_DOCX_SCRIPTS, 'unpack.py')
PACK_PY = os.path.join(_DOCX_SCRIPTS, 'pack.py')


# ── helpers ──────────────────────────────────────────────────────────────

def get_text(elem):
    """Combined text from all w:t children."""
    return ''.join(t.text or '' for t in elem.iter(f'{{{W}}}t'))


def set_text(para, new_text):
    """Replace paragraph text: set first w:t content, clear others."""
    runs = para.findall(f'./{{{W}}}r')
    if not runs:
        # Edge case: empty paragraph (e.g. blank line)
        r = etree.SubElement(para, f'{{{W}}}r')
        t = etree.SubElement(r, f'{{{W}}}t')
        t.text = new_text
        return
    ts = runs[0].findall(f'./{{{W}}}t')
    if ts:
        ts[0].text = new_text
    else:
        t = etree.SubElement(runs[0], f'{{{W}}}t')
        t.text = new_text
    for r in runs[1:]:
        for t in r.findall(f'./{{{W}}}t'):
            t.text = ''


def make_new_para(source_para, text):
    """Create a new w:p element by cloning source's w:pPr and setting text."""
    new_p = etree.Element(f'{{{W}}}p')
    ppr = source_para.find(f'{{{W}}}pPr')
    if ppr is not None:
        new_p.append(deepcopy(ppr))
    r = etree.SubElement(new_p, f'{{{W}}}r')
    t = etree.SubElement(r, f'{{{W}}}t')
    t.text = text
    return new_p


def load_structure(segments_dir):
    path = os.path.join(segments_dir, '_structure.json')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


# ── file collection ──────────────────────────────────────────────────────

def collect_md_files(segments_dir):
    """Walk segments_dir, return sorted list of (rel_path, filename, content)."""
    files = []
    for root, dirs, fnames in os.walk(segments_dir):
        for fn in sorted(fnames):
            if not fn.endswith('.md') or fn == '_revision_log.md':
                continue
            fpath = os.path.join(root, fn)
            rel = os.path.relpath(fpath, segments_dir)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read().rstrip('\n')
            files.append((rel, fn, content))
    return files


def categorize_md_files(files):
    """
    Separate MD files into updates dict and insertions dict.

    Returns:
        updates:  {paragraph_index: content}  for P\d{4}.md
        insertions: {after_idx: [content, ...]}  for P_new_\d+.md
    """
    updates = {}
    insertions = defaultdict(list)

    P_OLD = re.compile(r'^P(\d{4})\.md$')
    P_NEW = re.compile(r'^P_new_(\d{4,5})\.md$')

    for rel, fn, content in files:
        m = P_OLD.match(fn)
        if m:
            updates[int(m.group(1))] = content
            continue
        m = P_NEW.match(fn)
        if m:
            insertions[int(m.group(1))].append(content)

    return updates, dict(insertions)


# ── Phase 1: update existing paragraphs ─────────────────────────────────

def apply_text_updates(body_paras, updates):
    """Update text of existing paragraphs. Returns count of changes."""
    count = 0
    for idx, content in updates.items():
        if idx >= len(body_paras):
            continue
        current = get_text(body_paras[idx]).strip()
        if current != content:
            set_text(body_paras[idx], content)
            count += 1
    return count


# ── Phase 2: insert new paragraphs ──────────────────────────────────────

def insert_new_paragraphs(body_paras, insertions):
    """
    Insert new paragraphs after their anchor paragraphs.

    P_new_NNN is inserted after paragraph NNN in the body.
    Multiple new paragraphs after the same anchor maintain walk order.
    Handles out-of-range anchors by appending to body end.
    """
    body = body_paras[0].getparent() if body_paras else None
    if body is None or not insertions:
        return

    for after_idx in sorted(insertions.keys()):
        contents = insertions[after_idx]

        if after_idx >= len(body_paras):
            # Anchor doesn't exist — append at end
            for content in contents:
                last_para = body_paras[-1]
                new_p = make_new_para(last_para, content)
                body.append(new_p)
            continue

        target = body_paras[after_idx]
        # Insert in reverse order so that addnext produces correct sequence
        for content in reversed(contents):
            new_p = make_new_para(target, content)
            target.addnext(new_p)


# ── Phase 3: figure renumbering ─────────────────────────────────────────

def apply_figure_renumbering(doc_xml, structure):
    """Update all "图N" in-text references to match new figure numbering."""
    if not structure or not structure.get('figures'):
        return

    figures = structure['figures']
    # Build old→new mapping from _original_number (if any)
    renumber_map = {}
    for fig in figures:
        old_n = fig.get('_original_number')
        new_n = fig['number']
        if old_n is not None and old_n != new_n:
            renumber_map[old_n] = new_n

    if not renumber_map:
        return

    tree = etree.parse(doc_xml)
    root = tree.getroot()

    for t_elem in root.iter(f'{{{W}}}t'):
        if not t_elem.text:
            continue
        changed = False
        for old_n, new_n in renumber_map.items():
            pattern = rf'图{old_n}(?!\d)'
            replacement = f'图{new_n}'
            if re.search(pattern, t_elem.text):
                t_elem.text = re.sub(pattern, replacement, t_elem.text)
                changed = True
        # Also handle 表N references if tables were renumbered
        if changed:
            pass  # kept for future table renumbering

    tree.write(doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)


# ── Phase 4: repack ────────────────────────────────────────────────────

def repack(unpacked_dir, output_path, original_docx=None):
    """Run docx skill's pack.py."""
    cmd = [sys.executable, PACK_PY, unpacked_dir, output_path]
    if original_docx:
        cmd.extend(['--original', original_docx])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'WARNING: pack.py exited {result.returncode}')
        if result.stderr:
            print(f'  stderr: {result.stderr[:600]}')
    return result.returncode == 0


# ── main ─────────────────────────────────────────────────────────────────

def assemble_docx(unpacked_dir, segments_dir, output_docx_path, original_docx=None):
    """
    Full assembly pipeline:
      1. Update existing paragraph texts
      2. Insert new paragraphs
      3. Renumber figures
      4. Repack
    """
    doc_xml = os.path.join(unpacked_dir, 'word', 'document.xml')
    if not os.path.isfile(doc_xml):
        raise FileNotFoundError(f'{doc_xml} not found — run unpack.py first')

    tree = etree.parse(doc_xml)
    body = tree.getroot().find(f'{{{W}}}body')
    body_paras = body.findall(f'{{{W}}}p')

    # Parse segments
    md_files = collect_md_files(segments_dir)
    updates, insertions = categorize_md_files(md_files)

    print(f'  Existing paragraphs to update: {len(updates)}')
    print(f'  New paragraphs to insert:      {sum(len(v) for v in insertions.values())}')

    # Phase 1
    updated = apply_text_updates(body_paras, updates)
    print(f'  Text updates applied: {updated}')

    # Phase 2
    insert_new_paragraphs(body_paras, insertions)

    # Write Phase 1+2 results
    tree.write(doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    # Phase 3
    structure = load_structure(segments_dir)
    if structure and structure.get('figures'):
        apply_figure_renumbering(doc_xml, structure)
        print(f'  Figure references updated: {len(structure["figures"])} figures in structure')
    else:
        print('  No figure renumbering needed')

    # Phase 4
    print(f'  Packing → {output_docx_path}')
    repack(unpacked_dir, output_docx_path, original_docx=original_docx)

    print(f'Assembled: {output_docx_path}')


def main():
    if len(sys.argv) < 4:
        print(__doc__.strip())
        sys.exit(1)

    unpacked_dir = sys.argv[1]
    segments_dir = sys.argv[2]
    output_path = sys.argv[3]

    original_docx = None
    if '--original' in sys.argv:
        idx = sys.argv.index('--original')
        if idx + 1 < len(sys.argv):
            original_docx = sys.argv[idx + 1]

    if not os.path.isdir(unpacked_dir):
        print(f'Error: unpacked dir not found: {unpacked_dir}')
        sys.exit(1)
    if not os.path.isdir(segments_dir):
        print(f'Error: segments dir not found: {segments_dir}')
        sys.exit(1)

    assemble_docx(unpacked_dir, segments_dir, output_path, original_docx=original_docx)


if __name__ == '__main__':
    main()
