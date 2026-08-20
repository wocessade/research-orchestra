#!/usr/bin/env python3
"""
Validate the academic-coursework skill for cross-file consistency.

Checks:
  - YAML syntax
  - Stage file existence      (all file: paths)
  - next / route validity      (target must be in stages)
  - route completeness         (must have default; condition axis must be defined)
  - parallel_group validity    (group members + group_next exist)
  - dependency_graph           (all stages in manifest)
  - Gate ID                    (strategist gate references -> gate-chain.md)
  - SKILL.md file count        (matches actual strategists/ directory)
  - Dead stage files           (strategists/ files not in manifest)
  - entry_point matching       (stage entry_point in axes values)
  - Reference conditions       (referenced stages/axes exist)
  - always_load file existence (core files present)
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Need PyYAML: pip install pyyaml")
    sys.exit(1)

SKILL_DIR = Path(__file__).resolve().parent.parent
STAGES_DIR = SKILL_DIR / "strategists"
CORE_DIR = SKILL_DIR / "static" / "core"

errors = []
warnings = []

USE_EMOJI = False  # Windows compatibility
def X(): return "[X]"
def W(): return "[W]"

def err(msg): errors.append(f"{X()} {msg}")
def warn(msg): warnings.append(f"{W()} {msg}")

# ── 1. Load manifest ────────────────────────────────────────────────────

manifest_path = SKILL_DIR / "manifest.yaml"
if not manifest_path.exists():
    err(f"manifest.yaml not found at {manifest_path}")
    sys.exit(1)

try:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
except yaml.YAMLError as e:
    err(f"manifest.yaml YAML syntax error: {e}")
    sys.exit(1)

stages = manifest.get("strategists", {})
axes_def = manifest.get("axes", {})
dep_graph = manifest.get("dependency_graph", {})
references = manifest.get("references", {})

AXIS_NAMES = {k for k in axes_def if isinstance(axes_def[k], dict)}

# ── 2. Stage file existence ─────────────────────────────────────────────

for sid, sdata in stages.items():
    fpath = sdata.get("file", "")
    if not fpath:
        err(f"Stage {sid}: missing 'file' field")
        continue
    if not (SKILL_DIR / fpath).exists():
        err(f"Stage {sid}: file '{fpath}' not found")

# ── 3. next / route validity ────────────────────────────────────────────

for sid, sdata in stages.items():
    if "next" in sdata and sdata["next"] is not None:
        if sdata["next"] not in stages:
            err(f"Stage {sid}: next='{sdata['next']}' not in stages")

    if "route" in sdata:
        if not any("default" in item for item in sdata["route"]):
            err(f"Stage {sid}: route has no 'default' branch")
        for item in sdata["route"]:
            nxt = item.get("next")
            if nxt is not None and nxt not in stages:
                err(f"Stage {sid}: route -> '{nxt}' not in stages")
            cond = item.get("condition", {})
            ax = cond.get("axis")
            if ax and ax not in AXIS_NAMES:
                err(f"Stage {sid}: route axis '{ax}' not defined")

    cond = sdata.get("condition", {})
    if cond:
        ax = cond.get("axis")
        if ax and ax not in AXIS_NAMES:
            err(f"Stage {sid}: condition axis '{ax}' not defined")

    pg = sdata.get("parallel_group", [])
    for ps in pg:
        if ps not in stages:
            err(f"Stage {sid}: parallel_group '{ps}' not in stages")
    pgn = sdata.get("parallel_group_next")
    if pgn and pgn not in stages:
        err(f"Stage {sid}: parallel_group_next '{pgn}' not in stages")

# ── 4. dependency_graph consistency ──────────────────────────────────────

for gname, gstages in dep_graph.items():
    flat = []
    for gs in gstages:
        flat.extend(gs) if isinstance(gs, list) else flat.append(gs)
    for gs in flat:
        if gs not in stages:
            err(f"dependency_graph '{gname}': stage '{gs}' not in manifest")

# ── 5. Gate ID consistency ──────────────────────────────────────────────

gate_chain_path = CORE_DIR / "gate-chain.md"
if gate_chain_path.exists():
    gc_content = gate_chain_path.read_text(encoding="utf-8")
    gate_ids = set(re.findall(r"^\| (Q[\w-]+) \|", gc_content, re.MULTILINE))

    for sid, sdata in stages.items():
        fpath = sdata.get("file", "")
        full_path = SKILL_DIR / fpath
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        gate_match = re.search(r"\*\*Gate:\*\*\s*(Q[\w-]+)", content)
        if gate_match:
            gid = gate_match.group(1)
            if gid not in gate_ids:
                err(f"{sid} ({fpath}): gate '{gid}' not in gate-chain.md")
        else:
            warn(f"{sid} ({fpath}): no '**Gate:** Q...' header found")
else:
    warn("gate-chain.md not found")

# ── 6. SKILL.md file count ──────────────────────────────────────────────

skill_path = SKILL_DIR / "SKILL.md"
if skill_path.exists():
    skill_content = skill_path.read_text(encoding="utf-8")
    actual_count = len(list(STAGES_DIR.glob("*.md")))
    fc_match = re.search(r"strategists/ \((\d+) files\)", skill_content)
    if fc_match:
        declared = int(fc_match.group(1))
        if declared != actual_count:
            err(f"SKILL.md: declared {declared}, actual {actual_count}")
    else:
        warn("SKILL.md: no 'strategists/ (N files)' pattern found")

# ── 7. Dead stage files ─────────────────────────────────────────────────

manifest_files = {sdata["file"] for sdata in stages.values() if "file" in sdata}
actual_files = {f.relative_to(SKILL_DIR).as_posix() for f in STAGES_DIR.glob("*.md")}
for f in sorted(actual_files - manifest_files):
    warn(f"'{f}' exists in strategists/ but NOT in manifest strategists")

# ── 8. entry_point matching ─────────────────────────────────────────────

valid_eps = axes_def.get("entry_point", {}).get("values", []) if isinstance(axes_def.get("entry_point"), dict) else []
for sid, sdata in stages.items():
    ep = sdata.get("entry_point")
    if ep and ep not in valid_eps:
        err(f"Stage {sid}: entry_point='{ep}' not in {valid_eps}")

# ── 9. Reference conditions ─────────────────────────────────────────────

for ref_name, ref_data in references.items():
    if not isinstance(ref_data, dict):
        continue
    cond = ref_data.get("condition", {})
    if cond:
        stage_cond = cond.get("stage", [])
        if isinstance(stage_cond, str):
            stage_cond = [stage_cond]
        for s in stage_cond:
            if s not in stages:
                err(f"Ref '{ref_name}': condition stage '{s}' not in stages")
        ax = cond.get("axis")
        if ax and ax not in AXIS_NAMES:
            err(f"Ref '{ref_name}': condition axis '{ax}' not defined")

    ref_file = ref_data.get("file")
    if ref_file and not (SKILL_DIR / ref_file).exists():
        err(f"Ref '{ref_name}': file '{ref_file}' not found")

# ── 10. always_load file existence ──────────────────────────────────────

always_load = manifest.get("always_load", [])
for rel_path in always_load:
    if not (SKILL_DIR / rel_path).exists():
        if rel_path.startswith("static/core/"):
            err(f"always_load '{rel_path}' not found — core file missing")
        else:
            warn(f"always_load '{rel_path}' not found")

# ── 11. Non-axis condition keys in references ──────────────────────────

STANDARD_COND_KEYS = {"axis", "value", "stage", "file", "on_demand"}
for ref_name, ref_data in references.items():
    if not isinstance(ref_data, dict):
        continue
    cond = ref_data.get("condition", {})
    for key in cond:
        if key not in STANDARD_COND_KEYS and key not in AXIS_NAMES:
            warn(f"Ref '{ref_name}': condition key '{key}' is not a defined axis (shorthand for 'axis: {key}') — may be unreachable by validator")


# ── 12. Dependency graph entry reachability ────────────────────────────

STRATEGIST_ENTRY_POINTS = {
    sid for sid, sdata in stages.items()
    if sdata.get("entry_point")  # C1 has entry_point: course-assignment
}

def find_entry_stage(sid, visited=None):
    if visited is None:
        visited = set()
    if sid in visited:
        return False
    visited.add(sid)
    if sid in STRATEGIST_ENTRY_POINTS:
        return True
    for src_sid, src_data in stages.items():
        candidates = []
        if src_data.get("next") == sid:
            candidates.append(src_sid)
        if "route" in src_data:
            for r in src_data["route"]:
                if r.get("next") == sid:
                    candidates.append(src_sid)
                    break
        for c in candidates:
            if find_entry_stage(c, visited.copy()):
                return True
    return False

for gname, gstages in dep_graph.items():
    if not gstages:
        continue
    first = gstages[0]
    first_stage = first[0] if isinstance(first, list) else first
    if first_stage not in stages:
        continue
    if first_stage not in STRATEGIST_ENTRY_POINTS:
        if not find_entry_stage(first_stage):
            warn(f"dep_graph '{gname}': first stage '{first_stage}' has no entry_point and not reachable — graph may be unreachable")


# ── 13. Style rule conflict scan ──────────────────────────────────────────
# Known conflict fixtures: rules that should not contradict across references.
# Each fixture: (name, anti_pattern, pro_pattern, explanation)

CONFLICT_FIXTURES = [
    (
        "roadmap-paragraph",
        r"(?:delete|remove|no|cuts?|never|do\s*not|don'?t)[^\n]{0,80}roadmap\s*(?:paragraph|sentence)",
        r"(?:use|include|add|write|provide|keep|expected|introduce|present|structure|begin|start)[^\n]{0,80}roadmap\s*(?:paragraph|sentence)",
        "roadmap paragraph: some guides say DELETE, others say INCLUDE"
    ),
]

REF_DIR = SKILL_DIR / "references"
if REF_DIR.exists():
    for fixture_name, anti_pat, pro_pat, explanation in CONFLICT_FIXTURES:
        anti_files = []
        pro_files = []
        for ref_file in sorted(REF_DIR.rglob("*.md")):
            try:
                content = ref_file.read_text(encoding="utf-8")
            except Exception:
                continue
            # Case-insensitive search
            if re.search(anti_pat, content, re.IGNORECASE | re.DOTALL):
                anti_files.append(ref_file.relative_to(SKILL_DIR).as_posix())
            if re.search(pro_pat, content, re.IGNORECASE | re.DOTALL):
                pro_files.append(ref_file.relative_to(SKILL_DIR).as_posix())
        if anti_files and pro_files:
            warn(
                f"Conflict '{fixture_name}': {explanation}.\n"
                f"    Anti (delete/avoid): {', '.join(anti_files)}\n"
                f"    Pro (use/include): {', '.join(pro_files)}"
            )


# ── Summary ─────────────────────────────────────────────────────────────

print("=" * 60)
print("  Academic Coursework - Validation Report")
print(f"  Version: {manifest.get('version', 'unknown')}")
print(f"  Stages declared: {len(stages)}")
print(f"  Dependency graphs: {len(dep_graph)}")
print("=" * 60)

if errors:
    print(f"\n{len(errors)} ERROR(S):")
    for e in errors:
        print(f"  {e}")

if warnings:
    print(f"\n{len(warnings)} WARNING(S):")
    for w in warnings:
        print(f"  {w}")

if not errors and not warnings:
    print("\n[PASS] All validations passed.")

sys.exit(1 if errors else 0)
