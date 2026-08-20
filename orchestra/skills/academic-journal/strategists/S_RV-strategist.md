# Stage S_RV: Revision Verification [Strategist]

**Parent:** S_R Phase D

**Goal:** Run 5 automated checks on revised DOCX, produce `_verification_report.md`.

**Scripts used:**
- `docx_segmenter.py` — `validate_figures()` via python import（路径：`academic-shared/scripts/revision/`）
- Standard `grep` and `python` — text analysis

---

## Check A — Term Consistency

**Purpose:** Verify all old terms are fully replaced. No remnant of pre-revision terminology.

**Method:**
```
python -c "
# Read the applied_ops, extract old terms from global_replace ops
import json
with open('segments/_ops.json') as f:
    ops = json.load(f)
replacements = [op for op in ops if op.get('op') in ('global_replace', 'section_replace')]
print(f'Found {len(replacements)} replacement ops to verify')
for r in replacements:
    old = r['old']
    # Check all md files
    import os
    count = 0
    for root, dirs, fnames in os.walk('segments'):
        for fn in fnames:
            if fn.endswith('.md'):
                with open(os.path.join(root, fn)) as f:
                    content = f.read()
                count += content.count(old)
    verdict = 'PASS' if count == 0 else 'FAIL'
    print(f'  {verdict}: \"{old}\" — {count} remaining occurrences')
"
```

**Severity:** HIGH — remnant old terms mean incomplete replacement.

---

## Check B — Figure Number Continuity

**Purpose:** Verify figure numbers are sequential (1, 2, 3...N) with no gaps or duplicates, and paragraph ordering matches document order.

**Method:**
```python
# Import validate_figures from shared docx_segmenter.py
import sys, os, json
shared_scripts = os.path.join(
    os.path.dirname(__file__), '..', '..',
    'academic-shared', 'scripts', 'revision'
)
sys.path.insert(0, os.path.abspath(shared_scripts))
from docx_segmenter import validate_figures

with open('segments/_structure.json') as f:
    struct = json.load(f)

issues = validate_figures(struct.get('figures', []))
if issues:
    for issue in issues:
        print(f'  FAIL: {issue}')
else:
    print('  PASS: All figures sequential and properly ordered')
```

**Additional cross-reference check:**
```
grep -roh '图[0-9]\+' segments/ | sort -t图 -k2 -n | uniq > /tmp/fig_refs.txt
python -c "
with open('/tmp/fig_refs.txt') as f:
    refs = [int(line.strip()[1:]) for line in f if line.strip()]
max_ref = max(refs)
# Check for gaps in referenced numbers
all_nums = set(range(1, max_ref + 1))
referenced = set(refs)
missing = all_nums - referenced
if missing:
    print(f'WARN: Figure numbers never referenced in text: {sorted(missing)}')
else:
    print('PASS: All figure numbers 1..{max_ref} referenced at least once')
"
```

**Severity:** HIGH — broken figure numbering makes the paper unreadable.

---

## Check C — Text Deduplication

**Purpose:** Detect paragraphs with suspiciously high text overlap (>80% token overlap), which may indicate duplicate insertion.

**Method:**
```python
import os, re, json
from collections import defaultdict

segments_dir = 'segments/'
structure_path = os.path.join(segments_dir, '_structure.json')
with open(structure_path) as f:
    struct = json.load(f)

# Collect all non-heading, non-caption paragraphs
paragraphs = []  # [(rel_path, text)]
for root, dirs, fnames in os.walk(segments_dir):
    for fn in sorted(fnames):
        if not fn.endswith('.md') or fn == '_revision_log.md':
            continue
        fpath = os.path.join(root, fn)
        with open(fpath, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        if len(text) < 20:  # skip short paragraphs (headings, figure captions)
            continue
        rel = os.path.relpath(fpath, segments_dir)
        paragraphs.append((rel, text))

def tokenize(text):
    return set(re.findall(r'[\w一-鿿]+', text))

pairs = []
for i in range(len(paragraphs)):
    ti = tokenize(paragraphs[i][1])
    for j in range(i + 1, len(paragraphs)):
        tj = tokenize(paragraphs[j][1])
        overlap = len(ti & tj) / max(len(ti), len(tj))
        if overlap > 0.8:
            pairs.append((paragraphs[i][0], paragraphs[j][0], round(overlap, 2)))

if pairs:
    print(f'FAIL: {len(pairs)} paragraph pair(s) with >80% token overlap:')
    for a, b, score in pairs[:10]:
        print(f'  {a} <-> {b} ({score:.0%})')
else:
    print('PASS: No suspicious paragraph duplicates detected')
```

**Severity:** MEDIUM — duplicates affect readability but don't break structure.

---

## Check D — Section Integrity

**Purpose:** Verify every section directory has content (non-empty), and no section has lost all its paragraphs.

**Method:**
```python
import os, json

with open('segments/_structure.json') as f:
    struct = json.load(f)

sections = struct.get('sections', [])
empty_sections = []

def check_section(node, path_prefix='segments/'):
    sec_path = node.get('path', '')
    full_path = os.path.join(path_prefix, sec_path)
    has_content = False
    if os.path.isdir(full_path):
        for fn in os.listdir(full_path):
            if fn.endswith('.md'):
                has_content = True
                break
    if not has_content:
        empty_sections.append(node.get('heading', sec_path))
    for child in node.get('children', []):
        check_section(child, path_prefix)

for sec in sections:
    check_section(sec)

if empty_sections:
    print(f'FAIL: {len(empty_sections)} empty section(s):')
    for s in empty_sections:
        print(f'  - {s}')
else:
    print(f'PASS: All {len(sections)} section(s) have content')
```

**Severity:** MEDIUM — empty sections are incomplete but don't cause errors.

---

## Check E — Reference Integrity

**Purpose:** Verify all citation markers `[N]` or `[N,M]` or `[N-M]` refer to valid reference numbers.

**Method:**
```python
import os, re, json

# Get known reference max from the paper
# Strategy: extract all [N] patterns, find max, compare to cited refs
ref_pattern = re.compile(r'\[(\d+(?:[,\-\s]\d+)*)\]')
all_refs = set()

for root, dirs, fnames in os.walk('segments/'):
    for fn in fnames:
        if not fn.endswith('.md'):
            continue
        with open(os.path.join(root, fn), 'r', encoding='utf-8') as f:
            content = f.read()
        for match in ref_pattern.finditer(content):
            # Parse groups: [1,2,3] or [1-3] or [1]
            parts = match.group(1)
            for segment in re.split(r'[,\s]+', parts):
                segment = segment.strip()
                if '-' in segment:
                    start, end = segment.split('-')
                    all_refs.update(range(int(start), int(end) + 1))
                elif segment:
                    all_refs.add(int(segment))

if all_refs:
    max_ref = max(all_refs)
    missing = [n for n in range(1, max_ref + 1) if n not in all_refs]
    if missing:
        print(f'WARN: Gap in reference sequence: {missing[:20]} (of {max_ref})')
        # Check if this is intentional (1-page limit removal, etc.)
        print('  Note: gaps may be intentional if references were removed.')
    else:
        print(f'PASS: References 1..{max_ref} all cited sequentially')
else:
    print('WARN: No citation markers found (may not use [N] format)')

print(f'Total unique references cited: {len(all_refs)}')
```

**Severity:** MEDIUM — missing references are concerning but the paper still compiles.

---

## Report Format

Write `_verification_report.md` to segments/ directory:

```markdown
# Revision Verification Report

Checked: <timestamp>

## Summary
- [x] A. Term Consistency — <PASS|FAIL>
- [x] B. Figure Number Continuity — <PASS|FAIL>
- [x] C. Text Deduplication — <PASS|FAIL>
- [x] D. Section Integrity — <PASS|FAIL>
- [x] E. Reference Integrity — <PASS|FAIL>

Overall: <PASS | 2 HIGH issue(s) — Must Fix | N MEDIUM issue(s) — Optional>

## Details
<!-- Paste command outputs here -->

## Notes
<!-- Free-text observations -->
```

## Severity Resolution

| Result | Action |
|--------|--------|
| All PASS | Report success, revision complete |
| 0 HIGH + ≤5 MEDIUM | Show issues, ask user: accept or fix? |
| ≥1 HIGH | Must fix before acceptance. Flag each HIGH and the fix needed. |
| ≥6 MEDIUM | Ask user: batch fix or accept? |

## Programmatic Re-entry

If the user chooses to fix issues, the fixes are applied via S_R Phase C (not here). This strategist is read-only — it identifies issues without modifying any files.
