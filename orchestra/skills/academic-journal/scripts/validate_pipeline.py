#!/usr/bin/env python3
"""
Validate the academic-journal skill for cross-file consistency.

Checks:
  - YAML语法
  - Stage file 存在性      (所有 file: 路径)
  - next / route 指向有效性 (目标必须在 stages 中)
  - route 完整性            (必须有 default; condition axis 必须定义)
  - parallel_group 有效性   (组内 stage + group_next 都存在)
  - dependency_graph 一致性 (所有 stage 都在 manifest 中)
  - Gate ID                  (stage 文件顶部引用 → gate-chain.md 定义)
  - SKILL.md 文件计数        (与实际 strategists/ 目录一致)
  - Dead stage               (strategists/ 目录中未被 manifest 引用的文件)
  - entry_point 匹配         (stage 声明的 entry_point 必须在 axes 中)
  - reference 条件           (loading condition 引用的 stage 都存在)
  - stage 文件格式一致性     (是否有 Gate/Goal/Outputs 等元数据头)

Usage:
    python scripts/validate_pipeline.py

Report issues in English or Chinese as appropriate.
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 需要 PyYAML: pip install pyyaml")
    sys.exit(1)

SKILL_DIR = Path(__file__).resolve().parent.parent
STAGES_DIR = SKILL_DIR / "strategists"
CORE_DIR = SKILL_DIR / "static" / "core"
REFS_DIR = SKILL_DIR / "references"

errors = []
warnings = []


# ── Helpers ──────────────────────────────────────────────────────────────

import os

# Windows GBK terminal can't print emoji
USE_EMOJI = os.environ.get("TERM") != "cygwin" and os.name != "nt"

def X(): return "[X]" if not USE_EMOJI else "❌"
def W(): return "[W]" if not USE_EMOJI else "⚠️"

def err(msg: str):
    errors.append(f"{X()} {msg}")

def warn(msg: str):
    warnings.append(f"{W()} {msg}")


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
        continue


# ── 3. next / route validity ────────────────────────────────────────────

for sid, sdata in stages.items():
    # simple next
    if "next" in sdata and sdata["next"] is not None:
        if sdata["next"] not in stages:
            err(f"Stage {sid}: next='{sdata['next']}' not in stages definition")

    # route branches
    if "route" in sdata:
        if not any("default" in item for item in sdata["route"]):
            err(f"Stage {sid}: route has no 'default' branch")
        for item in sdata["route"]:
            nxt = item.get("next")
            if nxt is not None and nxt not in stages:
                err(f"Stage {sid}: route → '{nxt}' not in stages definition")
            cond = item.get("condition", {})
            ax = cond.get("axis")
            if ax and ax not in AXIS_NAMES:
                err(f"Stage {sid}: route condition axis '{ax}' not defined in axes")
            # check value validity (list or single)
            val = cond.get("value")
            if val and ax in AXIS_NAMES:
                allowed = axes_def[ax].get("values", [])
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    if v not in allowed:
                        warn(f"Stage {sid}: route condition value '{v}' not in axis '{ax}' allowed values {allowed}")

    # condition (conditional stage existence)
    cond = sdata.get("condition", {})
    if cond:
        ax = cond.get("axis")
        if ax and ax not in AXIS_NAMES:
            err(f"Stage {sid}: condition axis '{ax}' not defined")
        val = cond.get("value")
        if val and ax in AXIS_NAMES:
            allowed = axes_def[ax].get("values", [])
            if val not in allowed:
                warn(f"Stage {sid}: condition value '{val}' not in axis '{ax}' allowed values {allowed}")

    # merge flag
    if sdata.get("merge") and not sdata.get("entry_point"):
        warn(f"Stage {sid}: has merge=true but no entry_point — merge behavior ambiguous")

    # parallel_group
    pg = sdata.get("parallel_group", [])
    for ps in pg:
        if ps not in stages:
            err(f"Stage {sid}: parallel_group '{ps}' not in stages definition")
    pgn = sdata.get("parallel_group_next")
    if pgn and pgn not in stages:
        err(f"Stage {sid}: parallel_group_next '{pgn}' not in stages definition")


# ── 4. dependency_graph consistency ──────────────────────────────────────

for gname, gstages in dep_graph.items():
    flat = []
    for gs in gstages:
        if isinstance(gs, list):
            flat.extend(gs)
        else:
            flat.append(gs)
    for gs in flat:
        if gs not in stages:
            err(f"dependency_graph '{gname}': stage '{gs}' not in manifest stages")


# ── 5. Gate ID consistency ──────────────────────────────────────────────

gate_chain_path = CORE_DIR / "gate-chain.md"
if gate_chain_path.exists():
    gc_content = gate_chain_path.read_text(encoding="utf-8")
    # Extract gate IDs from gate-chain.md Gate Rules table
    gate_ids_in_chain = set(re.findall(r"^\| (Q[\w-]+) \|", gc_content, re.MULTILINE))
    # Also extract from the chain diagrams (Q1 → Q2 → ...)
    gate_ids_in_diagram = set(re.findall(r"Q[\w-]+", gc_content.split("## Gate Rules")[0] if "## Gate Rules" in gc_content else ""))

    all_defined_gates = gate_ids_in_chain | gate_ids_in_diagram

    for sid, sdata in stages.items():
        fpath = sdata.get("file", "")
        full_path = SKILL_DIR / fpath
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        gate_match = re.search(r"\*\*Gate:\*\*\s*(Q[\w-]+)", content)
        if gate_match:
            gid = gate_match.group(1)
            if gid not in all_defined_gates:
                err(f"{sid} ({fpath}): gate '{gid}' used in stage but not defined in gate-chain.md")
        else:
            warn(f"{sid} ({fpath}): no '**Gate:** Q...' header found")
else:
    warn("gate-chain.md not found — skipping gate consistency check")


# ── 6. SKILL.md file count ──────────────────────────────────────────────

skill_path = SKILL_DIR / "SKILL.md"
if skill_path.exists():
    skill_content = skill_path.read_text(encoding="utf-8")
    actual_stage_count = len(list(STAGES_DIR.glob("*.md")))
    fc_match = re.search(r"strategists/ \((\d+) files\)", skill_content)
    if fc_match:
        declared = int(fc_match.group(1))
        if declared != actual_stage_count:
            err(f"SKILL.md: stages count = {declared}, but strategists/ directory has {actual_stage_count} files")
    else:
        warn("SKILL.md: could not find 'strategists/ (N files)' pattern")
else:
    warn("SKILL.md not found")


# ── 7. Dead stage files ─────────────────────────────────────────────────

manifest_files = {sdata["file"] for sdata in stages.values() if "file" in sdata}
actual_files = {f.relative_to(SKILL_DIR).as_posix() for f in STAGES_DIR.glob("*.md")}
for f in sorted(actual_files - manifest_files):
    warn(f"Stage file '{f}' exists in strategists/ but is NOT declared in manifest.yaml stages")


# ── 8. entry_point matching ─────────────────────────────────────────────

valid_entry_points = axes_def.get("entry_point", {}).get("values", []) if isinstance(axes_def.get("entry_point"), dict) else []
for sid, sdata in stages.items():
    ep = sdata.get("entry_point")
    if ep:
        if ep not in valid_entry_points:
            err(f"Stage {sid}: entry_point='{ep}' not in axes.entry_point.values {valid_entry_points}")


# ── 9. Reference loading conditions ──────────────────────────────────────

for ref_name, ref_data in references.items():
    if not isinstance(ref_data, dict):
        continue
    cond = ref_data.get("condition", {})
    if not cond:
        continue
    stage_cond = cond.get("stage", [])
    if isinstance(stage_cond, str):
        stage_cond = [stage_cond]
    for s in stage_cond:
        if s not in stages:
            err(f"Reference '{ref_name}': condition stage '{s}' not in stages")

    # Check condition axis
    ax = cond.get("axis")
    if ax and ax not in AXIS_NAMES:
        err(f"Reference '{ref_name}': condition axis '{ax}' not defined")

    # Check reference file exists
    ref_file = ref_data.get("file")
    if ref_file and not (SKILL_DIR / ref_file).exists():
        err(f"Reference '{ref_name}': file '{ref_file}' not found")


# ── 10. Stage file header format consistency ────────────────────────────

for sid, sdata in stages.items():
    fpath = sdata.get("file", "")
    full_path = SKILL_DIR / fpath
    if not full_path.exists():
        continue
    content = full_path.read_text(encoding="utf-8")

    # Check for common header fields
    # Markdown bold format: **Field:** value — colon before closing **
    has_gate = bool(re.search(r"\*\*Gate:\*\*", content))
    has_goal = bool(re.search(r"\*\*Goal:\*\*", content))
    has_outputs = bool(re.search(r"\*\*Outputs?:\*\*", content))

    if not has_gate:
        warn(f"{sid} ({fpath}): missing '**Gate:**' header")
    if not has_goal:
        warn(f"{sid} ({fpath}): missing '**Goal:**' header")
    if not has_outputs:
        warn(f"{sid} ({fpath}): missing '**Outputs:**' header")


# ── 11. Gate IDs in quick-routing and paper-types ───────────────────────

quick_routing_path = REFS_DIR / "quick-routing.md"
if quick_routing_path.exists():
    qr_content = quick_routing_path.read_text(encoding="utf-8")
    # Check that routing references point to valid stages (S1, S0.5, C1, etc.)
    stage_refs = set(re.findall(r'\b(S[\d.]+|C[\d.]+|T[\d.]+|D[\d.]+)\b', qr_content))
    for sr in stage_refs:
        # filter short ones like "S1", "S2"
        if re.match(r'^[SCTD]\d', sr) and sr not in stages:
            warn(f"quick-routing.md: references stage '{sr}' not in manifest")


# ── 12. Style rule conflict scan ──────────────────────────────────────────

CONFLICT_FIXTURES = [
    (
        "roadmap-paragraph",
        r"(?:delete|remove|no|cuts?|never|do\s*not|don'?t)[^\n]{0,80}roadmap\s*(?:paragraph|sentence)",
        r"(?:use|include|add|write|provide|keep|expected|introduce|present|structure|begin|start)[^\n]{0,80}roadmap\s*(?:paragraph|sentence)",
        "roadmap paragraph: some guides say DELETE, others say INCLUDE"
    ),
]

if REFS_DIR.exists():
    for fixture_name, anti_pat, pro_pat, explanation in CONFLICT_FIXTURES:
        anti_files = []
        pro_files = []
        for ref_file in sorted(REFS_DIR.rglob("*.md")):
            try:
                content = ref_file.read_text(encoding="utf-8")
            except Exception:
                continue
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


# ── 13. Summary ─────────────────────────────────────────────────────────

PASS = "PASS" if not USE_EMOJI else "OK"
print("=" * 60)
print("  Academic Paper Pipeline - Validation Report")
print(f"  Pipeline version: {manifest.get('version', 'unknown')}")
print(f"  Stages declared: {len(stages)}")
print(f"  Dependency graphs: {len(dep_graph)}")
print(f"  References: {len(references)}")
print("=" * 60)

if errors:
    print(f"\n{len(errors)} ERROR(S) - must fix:")
    for e in errors:
        print(f"  {e}")

if warnings:
    print(f"\n{len(warnings)} WARNING(S) - review recommended:")
    for w in warnings:
        print(f"  {w}")

if not errors and not warnings:
    print(f"\n[{PASS}] All validations passed - no issues found.")

# ── 13. Agent count cross-validation ────────────────────────────────

CONFIG_DIR = SKILL_DIR / "evaluate" / "config"

def parse_agent_counts(config_dir):
    """Parse # @agent-count: N from YAML configs. Returns {tier: annotated_count}."""
    counts = {}
    for yf in sorted(config_dir.glob("*.yaml")):
        tier = yf.stem
        content = yf.read_text(encoding="utf-8")
        m = re.search(r'#\s*@agent-count:\s*(\d+)', content)
        if not m:
            warn(f"Config '{tier}.yaml': missing '# @agent-count: N' annotation")
            continue
        annotated = int(m.group(1))
        try:
            cfg = yaml.safe_load(content)
            dims = cfg.get("dimensions", [])
            actual = len(dims)
        except Exception:
            warn(f"Config '{tier}.yaml': could not parse YAML to validate dimension count")
            counts[tier] = annotated
            continue
        if annotated != actual:
            err(f"Config '{tier}.yaml': @agent-count={annotated} but dimensions count={actual}")
        else:
            counts[tier] = annotated
    return counts

agent_counts = parse_agent_counts(CONFIG_DIR)

# Cross-validate stale patterns in markdown files
# Journal verified: no stale agent-count references found during Mission 009 audit.
stale_patterns = []

for rel_path, pattern, msg in stale_patterns:
    full = SKILL_DIR / rel_path
    if full.exists():
        content = full.read_text(encoding="utf-8")
        if re.search(pattern, content):
            warn(msg)

# Check for orphaned configs
stage_agents_path = SKILL_DIR / "evaluate" / "stage_agents.md"
if stage_agents_path.exists():
    sa_content = stage_agents_path.read_text(encoding="utf-8")
    routed_tiers = set(re.findall(r'tier\s*=\s*`(\w+)`', sa_content))
    routed_tiers |= set(re.findall(r'tier = `{(\w+)}`', sa_content))
    # If stage_agents.md uses {degree} as dynamic tier, bachelor/master are implicit
    has_dynamic_degree = "degree" in routed_tiers
    implicit_tiers = {"bachelor", "master"} if has_dynamic_degree else set()
    for tier in agent_counts:
        if tier not in routed_tiers and tier not in implicit_tiers:
            warn(f"Config '{tier}.yaml' has @agent-count but tier '{tier}' is not routed in stage_agents.md")
    if "bachelor" in agent_counts and "bachelor" not in routed_tiers:
        warn(f"Config 'bachelor.yaml' has @agent-count={agent_counts['bachelor']} but is orphaned — never routed to by stage_agents.md")


# ── 14. always_load file existence ──────────────────────────────────────

always_load = manifest.get("always_load", [])
for rel_path in always_load:
    full = SKILL_DIR / rel_path
    if not full.exists():
        if rel_path.startswith("static/core/"):
            err(f"always_load '{rel_path}' not found — core file missing")
        else:
            warn(f"always_load '{rel_path}' not found")


# ── 15. Evaluate agent file existence ───────────────────────────────────

AGENTS_DIR = SKILL_DIR / "evaluate" / "agents"
HUMANITIES_DIR = AGENTS_DIR / "humanities"
STEM_DIR = AGENTS_DIR / "stem"


def check_agent_file(agent_id: str, tier: str, config_name: str):
    """Check that an agent file exists at the correct path for its tier."""
    if tier in ("humanities_bachelor",):
        agent_path = HUMANITIES_DIR / f"{agent_id}.md"
    elif tier in ("stem_bachelor",):
        agent_path = STEM_DIR / f"{agent_id}.md"
    else:
        agent_path = AGENTS_DIR / f"{agent_id}.md"
    if not agent_path.exists():
        fallback = AGENTS_DIR / f"{agent_id}.md"
        if not fallback.exists():
            err(f"Config '{config_name}': agent '{agent_id}' not found at {agent_path.relative_to(SKILL_DIR)} (or {fallback.relative_to(SKILL_DIR)})")


for yf in sorted(CONFIG_DIR.glob("*.yaml")):
    try:
        cfg = yaml.safe_load(yf.read_text(encoding="utf-8"))
    except Exception:
        warn(f"Config '{yf.stem}.yaml': could not parse YAML to validate agents")
        continue
    if not isinstance(cfg, dict):
        continue
    tier = cfg.get("tier", yf.stem)
    for dim in cfg.get("dimensions", []):
        for agent_id in dim.get("agents", []):
            check_agent_file(agent_id, tier, yf.stem)


# ── 16. Dependency graph ordering vs route logic ────────────────────────

for gname, gstages in dep_graph.items():
    flat = []
    for gs in gstages:
        if isinstance(gs, list):
            flat.extend(gs)
        else:
            flat.append(gs)
    for i in range(len(flat) - 1):
        a, b = flat[i], flat[i + 1]
        if a not in stages or b not in stages:
            continue
        sdata = stages[a]
        can_reach = sdata.get("next") == b
        if not can_reach and "route" in sdata:
            can_reach = any(r.get("next") == b for r in sdata["route"])
        if not can_reach and sdata.get("parallel_group_next") == b:
            can_reach = True
        if not can_reach and b in sdata.get("parallel_group", []):
            can_reach = True
        if not can_reach:
            warn(f"dep_graph '{gname}': '{a}'→'{b}' — '{a}'.next/route doesn't directly point to '{b}'. Verify intentional.")


# ── 17. Config dimension weight sum ─────────────────────────────────────

for yf in sorted(CONFIG_DIR.glob("*.yaml")):
    try:
        cfg = yaml.safe_load(yf.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(cfg, dict):
        continue
    dims = cfg.get("dimensions", [])
    total_weight = sum(d.get("weight", 0) for d in dims)
    if abs(total_weight - 1.0) > 0.01:
        warn(f"Config '{yf.stem}.yaml': dimension weights sum to {total_weight:.3f}, expected ~1.0")


# ── 18. Reference condition axis value validity ─────────────────────────

for ref_name, ref_data in references.items():
    if not isinstance(ref_data, dict):
        continue
    cond = ref_data.get("condition", {})
    ax = cond.get("axis")
    val = cond.get("value")
    if ax and ax in AXIS_NAMES and val is not None:
        allowed = axes_def[ax].get("values", [])
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            if v not in allowed:
                warn(f"Reference '{ref_name}': condition value '{v}' not in axis '{ax}' allowed values {allowed}")


# ── 19. Stage route vs next mutual exclusion ────────────────────────────

for sid, sdata in stages.items():
    if "next" in sdata and "route" in sdata and sdata["next"] is not None:
        err(f"Stage {sid}: has both 'next' ({sdata['next']}) and 'route' — ambiguous")


# ── 20. Non-axis condition keys in references ─────────────────────────

STANDARD_COND_KEYS = {"axis", "value", "stage", "file", "on_demand"}
for ref_name, ref_data in references.items():
    if not isinstance(ref_data, dict):
        continue
    cond = ref_data.get("condition", {})
    for key in cond:
        if key not in STANDARD_COND_KEYS and key not in AXIS_NAMES:
            warn(f"Reference '{ref_name}': condition key '{key}' is not a defined axis (shorthand for 'axis: {key}') — may be unreachable by validator")


# ── 21. Dependency graph entry reachability ────────────────────────────

STRATEGIST_ENTRY_POINTS = {
    sid for sid, sdata in stages.items()
    if sdata.get("entry_point")
}

def find_entry_stage(sid, visited=None):
    """Walk backwards through next/route to find if any entry point can reach sid."""
    if visited is None:
        visited = set()
    if sid in visited:
        return False
    visited.add(sid)
    if sid in STRATEGIST_ENTRY_POINTS:
        return True
    # Find all stages that point to sid
    for src_sid, src_data in stages.items():
        candidates = []
        if src_data.get("next") == sid:
            candidates.append(src_sid)
        if "route" in src_data:
            for r in src_data["route"]:
                if r.get("next") == sid:
                    candidates.append(src_sid)
                    break
        for ps in src_data.get("parallel_group", []):
            if ps == sid:
                candidates.append(src_sid)
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
    # Check: is first_stage itself an entry point, OR reachable from one?
    if first_stage not in STRATEGIST_ENTRY_POINTS:
        if not find_entry_stage(first_stage):
            warn(f"dep_graph '{gname}': first stage '{first_stage}' has no entry_point and is not reachable from any entry point — graph may be unreachable")


# ── End of checks ──────────────────────────────────────────────────────

sys.exit(1 if errors else 0)
