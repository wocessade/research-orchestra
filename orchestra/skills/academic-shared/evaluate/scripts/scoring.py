#!/usr/bin/env python3
"""scoring.py — Weighted scoring engine for the evaluate module.

Reads tier config YAML + agent report files, computes dimension scores,
weighted total, grade mapping, gate blocker detection, and generates
report.md and report.json.

Usage:
    python scoring.py --tier course --config-dir <path> \
        --agent-reports-dir <path> --output-dir <path> \
        [--calibration <path>] [--previous-report-dir <path>]
"""

import argparse
import json
import os
import re
import math
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


DIMENSION_SCORE_RE = re.compile(r"DIMENSION_SCORE(?:\s+\S+)?\s*:\s*(\d+(?:\.\d+)?)")
CONFIDENCE_SCORE_RE = re.compile(r"CONFIDENCE_SCORE\s*:\s*(\d+(?:\.\d+)?)(?:\s|$)")
LOW_CONFIDENCE_THRESHOLD = 5.0
ISSUE_RE = re.compile(r"\[(Critical|Major|Minor)\]\s*(.*?)(?=\n\[|\n\n|\Z)", re.DOTALL)
BLOCKER_KEYWORDS = {
    "missing_required_section": [
        "缺少章节", "missing section", "required section missing",
        "无摘要", "无引言", "无结论", "无参考文献",
    ],
    "pervasive_ai_tone": [
        "大面积AI痕迹", "pervasive AI", "全文AI生成痕迹",
        "全篇AI生成痕迹", "人工无法区分",
    ],
    "insufficient_page_count": [
        "页数不足", "insufficient page", "页数不达标",
    ],
    "logic_contradiction": [
        "逻辑矛盾", "internal contradiction", "自相矛盾",
        "论证链断裂", "前后矛盾",
    ],
    "plagiarism_risk_high": [
        "高度抄袭风险", "high plagiarism risk", "大面积未引用的原文",
        "疑似抄袭", "抄袭风险", "剽窃",
        "未标引的原文引用", "未标引的引用", "无引用的原文",
    ],
    "insufficient_innovation": [
        "创新不足", "缺乏创新", "无新意", "重复现有研究",
        "无原创性",
    ],
    "missing_core_section": [
        "缺少核心章节", "核心章节缺失", "missing core chapter",
    ],
    "insufficient_references": [
        "参考文献不足", "insufficient references", "参考文献数量不足",
        "参考文献数量为0", "参考文献列表空白", "无参考文献列表",
        "引文标注缺失", "无具体引文", "无任何引文标注",
        "引用数量为0", "reference_list_empty",
    ],
    # ── Humanities-specific blockers ──
    "no_literature_review_chapter": [
        "缺少文献综述", "无文献综述", "文献综述缺失",
        "缺少独立的文献综述", "missing literature review",
    ],
    "no_theory_framework": [
        "无理论框架", "理论框架缺失", "理论未使用",
        "理论仅被提及", "缺乏理论视角",
    ],
    "critical_argument_gap": [
        "无核心论点", "核心论点缺失", "论点不可辩护",
        "论证关键缺失", "无独立论点",
    ],
    "insufficient_primary_sources": [
        "一手文献不足", "原著引用不足", "缺乏对原典的分析",
        "未引用原著", "一手文献缺失",
    ],
    # ── STEM-specific blockers (merged with common) ──
    "methodology_fatal": [
        "方法论缺陷", "方法根本错误", "不可复现", "无研究方法", "无实验方法",
    ],
    "data_integrity_risk": [
        "数据疑似编造", "结果不可信", "数据前后矛盾", "数据真实性存疑",
    ],
    "missing_data_analysis": [
        "缺少数据分析", "未分析数据", "仅有描述无分析",
    ],
    "no_research_question": [
        "无研究问题", "无明确研究目的", "研究目标缺失",
    ],
    "factual_error": [
        "事实错误", "factual error", "章节数不符", "数量不一致",
        "数字矛盾", "术语不一致", "交叉引用无效", "引用不存在的图",
        "引用不存在的表", "前后数据矛盾", "实际为", "不存在",
    ],
}


def load_config(config_dir, tier):
    """Load tier config YAML file."""
    path = Path(config_dir) / f"{tier}.yaml"
    if not path.exists():
        print(f"ERROR: Config file not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_agent_score(report_path):
    """Extract DIMENSION_SCORE from an agent report file."""
    if not Path(report_path).exists():
        print(f"WARNING: Agent report not found: {report_path}")
        return None
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    match = DIMENSION_SCORE_RE.search(content)
    if match:
        return float(match.group(1))
    heuristic = heuristic_score(content)
    print(f"WARNING: DIMENSION_SCORE not found in {report_path}, using heuristic: {heuristic}")
    return heuristic


VARIANCE_THRESHOLD = 15  # Max-min gap on 0-100 scale — above this = unstable agent


def parse_agent_scores_triplicate(reports_dir, agent_id):
    """Try to read 3 runs of an agent report, compute variance and median.

    Returns:
        (median_score: float|None, variance_high: bool, scores: list[float], median_confidence: float|None)
    """
    scores = []
    confidences = []
    for i in range(1, 4):
        path = Path(reports_dir) / f"{agent_id}_review_{i}.md"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                content = f.read()
            m = DIMENSION_SCORE_RE.search(content)
            if m:
                scores.append(float(m.group(1)))
            cm = CONFIDENCE_SCORE_RE.search(content)
            if cm:
                confidences.append(float(cm.group(1)))
    if not scores:
        # Fall back to single file
        single = Path(reports_dir) / f"{agent_id}_review.md"
        if single.exists():
            score = parse_agent_score(str(single))
            single_confidence = None
            if single.exists():
                with open(single, encoding="utf-8") as f:
                    sc = CONFIDENCE_SCORE_RE.search(f.read())
                    if sc:
                        single_confidence = float(sc.group(1))
            return (score, False, [score] if score else [], single_confidence)
        return (None, False, [], None)

    scores.sort()
    n = len(scores)
    median = scores[n // 2] if n % 2 else (scores[n // 2 - 1] + scores[n // 2]) / 2
    variance_high = (max(scores) - min(scores)) > VARIANCE_THRESHOLD

    # Compute median confidence
    if confidences:
        confidences.sort()
        median_confidence = confidences[len(confidences) // 2]
    else:
        median_confidence = None

    if n < 3:
        print(f"  WARNING: {agent_id} has {n}/3 runs, expected triplicate")

    return (median, variance_high, scores, median_confidence)


def run_text_stats(text_path):
    """Run text_stats.py as subprocess and return parsed stats dict."""
    script_path = Path(__file__).parent / "text_stats.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), text_path],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"WARNING: text_stats.py failed: {e}")
        return {}


def fuse_ai_penalty(agent_ai_score, script_stats, fusion_config):
    """Confidence-weighted AI penalty fusion.

    Four cases:
    1. Both say AI (agent<60 + signal>=threshold) → keep agent score (full penalty)
    2. Both say no AI (agent>=60 + signal<threshold) → keep agent score (no change)
    3. Agent misses AI (agent>=60 + signal>=threshold) → pull down toward 50
    4. Agent over-sensitive (agent<60 + signal<threshold) → pull up toward 50

    fusion_config keys:
      script_keys, thresholds, agreement_threshold (default 0.5),
      disagree_shrink (default 0.3), low_signal_shrink (default 0.4)
    """
    if not script_stats or not fusion_config:
        return agent_ai_score

    keys = fusion_config.get("script_keys", [])
    thresholds = fusion_config.get("thresholds", {})
    if not keys:
        return agent_ai_score

    signals = 0
    total = 0
    for key in keys:
        val = script_stats.get(key, 0)
        thresh = thresholds.get(key, 5.0)
        total += 1
        if isinstance(thresh, dict):
            # Bidirectional threshold: triggers when value is OUTSIDE [low, high]
            low = thresh.get("low", -float("inf"))
            high = thresh.get("high", float("inf"))
            if val < low or val > high:
                signals += 1
        elif val > thresh:
            signals += 1

    signal_strength = signals / total if total > 0 else 0
    threshold = fusion_config.get("agreement_threshold", 0.5)

    agent_signals_ai = agent_ai_score < 60          # Agent thinks it's AI?
    script_signals_ai = signal_strength >= threshold # Script thinks it's AI?

    if agent_signals_ai == script_signals_ai:
        # Agreement: both say AI or both say no AI — keep agent score
        return agent_ai_score
    elif script_signals_ai and not agent_signals_ai:
        # Script says AI but agent doesn't: pull down toward 50
        shrink = fusion_config.get("disagree_shrink", 0.3)
        return agent_ai_score - (agent_ai_score - 50) * shrink * signal_strength
    else:
        # Agent says AI but script doesn't confirm: pull up toward 50
        shrink = fusion_config.get("low_signal_shrink", 0.4)
        correction = (50 - agent_ai_score) * shrink * (1 - signal_strength)
        return agent_ai_score + correction


def run_content_depth(text_path):
    """Run content_depth.py as subprocess and return parsed result dict."""
    script_path = Path(__file__).parent / "content_depth.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), text_path],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"WARNING: content_depth.py failed: {e}")
        return {"metrics": {}, "warnings": []}


def evaluate_paper_length(char_count, tier_config):
    """Evaluate if paper length is appropriate. Returns (modifier, warning).
    modifier: negative value (-5 to 0) applied to content dimension.
    tier_config may contain length_limits: {min, max, too_short_penalty, too_long_penalty}
    """
    limits = tier_config.get("length_limits", {})
    min_chars = limits.get("min", 8000)
    max_chars = limits.get("max", 50000)
    too_short_factor = limits.get("too_short_penalty", 0.006)
    too_long_factor = limits.get("too_long_penalty", 0.001)

    if char_count < min_chars:
        deficit = min_chars - char_count
        penalty = min(10, deficit / 1000 * too_short_factor * 10)
        return round(-penalty, 1), f"论文偏短({char_count}字，少于{min_chars}字标准)"
    elif char_count > max_chars:
        excess = char_count - max_chars
        penalty = min(5, excess / 1000 * too_long_factor * 10)
        return round(-penalty, 1), f"论文偏长({char_count}字，超过{max_chars}字标准)"
    return 0, None


def clamp_curve_cap(ai_tone, cfg):
    """Convex exponential release curve for clamp_max.
    ai_tone=0 → cap=base_cap; ai_tone→∞ → cap→100.
    cfg keys: base_cap (default 40), release_rate (default 0.05)
    """
    base = cfg.get("base_cap", 40)
    rate = cfg.get("release_rate", 0.05)
    return round(base + (100 - base) * (1 - math.exp(-rate * ai_tone)), 1)


def heuristic_score(content):
    """Fallback heuristic: estimate score from issue count."""
    critical = len(re.findall(r"\[Critical\]", content))
    major = len(re.findall(r"\[Major\]", content))
    minor = len(re.findall(r"\[Minor\]", content))
    score = 100 - critical * 15 - major * 7 - minor * 2
    return max(60, min(100, score))


def power_scale_mapping(raw, cfg):
    """Continuous power-scale mapping.
    cfg: {type: power_scale, floor: 40, threshold: 20, exponent: 0.5}
    Maps raw [0-100] → mapped [floor-100] with power curve above threshold.
    """
    floor = cfg.get("floor", 0)
    threshold = cfg.get("threshold", 0)
    exponent = cfg.get("exponent", 0.5)
    if raw <= threshold:
        return float(floor)
    scaled = (raw - threshold) / (100 - threshold)
    return round(floor + (100 - floor) * (scaled ** exponent), 1)


def apply_score_mapping(raw_score, mapping_config):
    """Apply tier-specific score mapping to a dimension score.

    mapping_config example:
      {type: elevate_baseline, floor: 40,
       segments: [{raw: [0,20], mapped: [40,40]}, ...]}
    """
    if mapping_config is None:
        return raw_score
    mtype = mapping_config.get("type", "")
    if mtype == "power_scale":
        return power_scale_mapping(raw_score, mapping_config)
    # Legacy segment-based mapping
    floor = mapping_config.get("floor", 0)
    for segment in mapping_config.get("segments", []):
        raw_low, raw_high = segment["raw"]
        map_low, map_high = segment["mapped"]
        if raw_low <= raw_score <= raw_high:
            denom = raw_high - raw_low
            ratio = (raw_score - raw_low) / denom if denom > 0 else 0
            return max(floor, map_low + ratio * (map_high - map_low))
    return max(floor, raw_score)


def apply_coupling(dim_scores, coupling_rules, dimensions):
    """Apply all coupling rules to dimension scores. Returns (dim_scores, weights).

    Modifies dim_scores in place for clamp_max and divergence_penalty rules.
    Returns adjusted weights dict for dynamic_weight rules.
    """
    weights = {dim["id"]: dim["weight"] for dim in dimensions}

    for rule in coupling_rules:
        rule_type = rule.get("type", "")

        if rule_type == "clamp_max":
            source_id = rule["source"]
            ai = dim_scores.get(source_id, 100)
            target_ids = rule.get("targets", [])
            if "base_cap" in rule:
                # Continuous exponential release curve
                cap = clamp_curve_cap(ai, rule)
                for target_id in target_ids:
                    if target_id in dim_scores and dim_scores[target_id] is not None:
                        dim_scores[target_id] = min(dim_scores[target_id], cap)
            elif "zones" in rule:
                # Legacy zone-based clamping (backward compatible)
                for target_id in target_ids:
                    if target_id not in dim_scores or dim_scores[target_id] is None:
                        continue
                    for zone in rule.get("zones", []):
                        if ai <= zone["ai_max"]:
                            if "target_max_offset" in zone:
                                cap = ai + zone["target_max_offset"]
                            else:
                                cap = zone["target_max"]
                            dim_scores[target_id] = min(dim_scores[target_id], cap)
                            break

        elif rule_type == "divergence_penalty":
            source_a, source_b = rule["sources"]
            val_a = dim_scores.get(source_a, 50)
            val_b = dim_scores.get(source_b, 50)
            diff = val_a - val_b
            cond = rule["condition"]
            if diff > cond["min_divergence"] and val_b < cond["target_max_for_penalty"]:
                penalty = min(diff * rule["penalty_factor"], rule["max_penalty"])
                target = rule["target"]
                if target in dim_scores and dim_scores[target] is not None:
                    dim_scores[target] = max(0, dim_scores[target] - penalty)

        elif rule_type == "dynamic_weight":
            ai = dim_scores.get("ai_tone", 100)
            innov = dim_scores.get("innovation", 0)
            resolved = None
            for mapping in rule.get("mapping", []):
                if eval_condition(mapping["condition"], ai, innov):
                    resolved = mapping
                    break
            if resolved:
                weights[rule["target"]] = resolved["weight"]
                bf = resolved.get("borrow_from", {})
                if isinstance(bf, dict):
                    for dim_id, delta in bf.items():
                        if dim_id in weights:
                            weights[dim_id] += delta
                gt = resolved.get("give_to", {})
                if isinstance(gt, dict):
                    for dim_id, delta in gt.items():
                        if dim_id in weights:
                            weights[dim_id] += delta
            else:
                weights[rule["target"]] = rule.get("default_weight", weights[rule["target"]])

    return dim_scores, weights


def eval_condition(condition_str, ai_tone, innovation):
    """Evaluate a simple condition string like 'ai_tone >= 70 && innovation >= 70'."""
    env = {"ai_tone": ai_tone, "innovation": innovation}
    py_expr = condition_str.replace("&&", " and ")
    try:
        return bool(eval(py_expr, {"__builtins__": {}}, env))
    except Exception:
        return False


AI_MARKERS_RE = re.compile(r"AI_MARKERS:\s*\n(.*?)(?=\n\S|\Z)", re.DOTALL)


def parse_ai_markers(report_path):
    """Extract AI_MARKERS keyword counts from ai_tone_detector report."""
    if not Path(report_path).exists():
        return {}
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    m = AI_MARKERS_RE.search(content)
    if not m:
        return {}
    markers = {}
    for line in m.group(1).strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            try:
                markers[key.strip().replace("_count", "")] = int(val.strip())
            except ValueError:
                pass
    return markers


DEEP_PATTERNS_RE = re.compile(r"DEEP_PATTERNS:\s*\n(.*?)(?=\n\S|\Z)", re.DOTALL)
DEEP_PATTERN_KEYS = [
    "homogeneity", "abstract_patchwork",
    "discussion_shallow", "acknowledgment_template",
]
# Per-pattern level→penalty map. Level from agent DEEP_PATTERNS output.
# All levels not listed (or unrecognized) → penalty = 0.
DEEP_PATTERN_LEVEL_MAP = {
    "abstract_patchwork": {"none": 0, "low": 2, "medium": 5, "high": 7, "severe": 9},
    "homogeneity":        {"none": 0, "low": 2, "medium": 5, "high": 7},
    "discussion_shallow": {"none": 0, "low": 2, "medium": 4, "high": 6, "severe": 7},
    "acknowledgment_template": {"none": 0, "low": 1, "medium": 2, "high": 3},
}
LEVEL_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "severe": 4}


def parse_deep_patterns(report_path):
    """Extract DEEP_PATTERNS level findings from an agent report.

    Returns dict of {pattern_key: level_str}. Patterns not found = "none".
    """
    if not Path(report_path).exists():
        return {}
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    m = DEEP_PATTERNS_RE.search(content)
    if not m:
        return {}
    patterns = {}
    for line in m.group(1).strip().split("\n"):
        line = line.strip()
        if ":" in line and "_evidence" not in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().lower()
            if key in DEEP_PATTERN_KEYS:
                patterns[key] = val
    return patterns


def deep_pattern_deduction(found_levels):
    """Compute total deduction from deep pattern findings.

    found_levels: dict of {pattern_key: level_str}
    Returns (total_deduction, details_list)
    """
    total = 0
    details = []
    for k in DEEP_PATTERN_KEYS:
        level = found_levels.get(k, "none")
        pmap = DEEP_PATTERN_LEVEL_MAP.get(k, {})
        penalty = pmap.get(level, 0)
        if penalty > 0:
            total += penalty
            details.append(f"{k}={penalty} ({level})")
    return total, details


def sigmoid_penalty(count, weight, inflection, steepness):
    """Sigmoid curve penalty.

    Near 0 when count << inflection, near weight when count >> inflection.
    """
    return weight / (1 + math.exp(-steepness * (count - inflection)))


def inverted_sigmoid_penalty(count, weight, inflection, steepness):
    """Inverted sigmoid: near weight when count=0, near 0 when count >> inflection.

    Use for signals where LOW count = AI pattern (e.g., zero causal conjunctions).
    """
    return weight - sigmoid_penalty(count, weight, inflection, steepness)


def compute_ai_curve_penalty(markers, curves_config, discipline="general"):
    """Compute total AI tone penalty from keyword counts and curve config.

    Normalizes keyword counts to per-10K-char density when character_count
    is available in markers. Returns total deduction (0-100).

    When discipline="stem", applies per-curve stem overrides (e.g. higher
    inflection for 进行/该X in engineering papers).
    """
    if not curves_config or not markers:
        return 0.0
    char_count = markers.get("character", 0) or markers.get("character_count", 0) or 0
    total = 0.0
    for key, cfg in curves_config.items():
        count = markers.get(key, 0)
        ctype = cfg.get("curve", "sigmoid")
        if ctype not in ("sigmoid", "inverted_sigmoid"):
            continue
        # Apply discipline-specific overrides
        if discipline == "stem" and "stem" in cfg:
            inflection = cfg["stem"].get("inflection", cfg.get("inflection", 10))
        else:
            inflection = cfg.get("inflection", 10)
        if char_count > 0:
            density = count / (char_count / 10000)
        else:
            density = count
        if ctype == "inverted_sigmoid":
            total += inverted_sigmoid_penalty(
                density,
                cfg.get("weight", 0),
                inflection,
                cfg.get("steepness", 0.3),
            )
        else:
            total += sigmoid_penalty(
                density,
                cfg.get("weight", 0),
                inflection,
                cfg.get("steepness", 0.3),
            )
    return round(total, 1)


def parse_issues(report_path, agent_id, dimension_id):
    """Extract issues tagged with [Critical/Major/Minor] from an agent report."""
    if not Path(report_path).exists():
        return []
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    issues = []
    matches = ISSUE_RE.finditer(content)
    for m in matches:
        severity = m.group(1).strip()
        description = m.group(2).strip()
        issues.append({
            "severity": severity,
            "location": "",
            "description": description,
            "quote": "",
            "agent": agent_id,
            "dimension": dimension_id,
        })
    return issues


def compute_weighted_total(dim_scores, dimensions):
    """Compute weighted total score from dimension scores and weights."""
    total = 0.0
    for dim in dimensions:
        dim_id = dim["id"]
        if dim_id in dim_scores and dim_scores[dim_id] is not None:
            total += dim_scores[dim_id] * dim["weight"]
    return round(total, 1)


def map_to_grade(score, thresholds):
    """Map a numerical score to a letter grade based on thresholds.

    thresholds: {"优": 90, "良": 75, "中": 60, "差": 0}
    """
    for grade, threshold in sorted(thresholds.items(), key=lambda x: -x[1]):
        if score >= threshold and threshold > 0:
            return grade
    return "差"


def compute_convergence(current_issues, prev_report_path, convergence_config, round_num):
    """Compare current issues against previous round to determine convergence.

    Returns dict with convergence status and details.
    """
    if round_num <= 1 or not prev_report_path or not Path(prev_report_path).exists():
        return {"status": "first_round", "round": round_num, "note": "First round — no convergence check."}

    try:
        with open(prev_report_path, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception as e:
        return {"status": "error", "round": round_num, "note": f"Could not load previous report: {e}"}

    prev_issues = prev.get("issues", [])
    prev_issue_descs = {i.get("description", "")[:120] for i in prev_issues}

    # Count new issues (not present in previous round)
    new_critical = 0
    new_major = 0
    new_minor = 0
    for issue in current_issues:
        desc = issue.get("description", "")[:120]
        if desc in prev_issue_descs:
            continue
        sev = issue.get("severity", "")
        if sev == "Critical":
            new_critical += 1
        elif sev == "Major":
            new_major += 1
        elif sev == "Minor":
            new_minor += 1

    # Check convergence criteria
    cc = convergence_config.get("converged_when", {}) if convergence_config else {}
    max_critical = cc.get("new_critical", 0)
    max_major_str = cc.get("new_major", "<= 2")

    if isinstance(max_major_str, str) and "<=" in max_major_str:
        max_major = int(max_major_str.replace("<=", "").strip())
    else:
        max_major = int(max_major_str)

    max_rounds = convergence_config.get("max_rounds", 3) if convergence_config else 3
    degeneration_stop = convergence_config.get("degeneration_stop", True) if convergence_config else True

    # Degeneration check: compare prev round's issues against prev-prev
    # For simplicity, check if current critical count grew vs previous
    prev_critical = sum(1 for i in prev_issues if i.get("severity") == "Critical")
    prev_major = sum(1 for i in prev_issues if i.get("severity") == "Major")

    degenerated = False
    if degeneration_stop and round_num >= 3 and new_critical > prev_critical:
        degenerated = True

    status = "CONTINUE"
    note = ""

    if degenerated:
        status = "DEGENERATED"
        note = "Previously fixed issues have reappeared. Stop iterating and re-examine the fix approach."
    elif new_critical <= max_critical and new_major <= max_major:
        status = "CONVERGED"
        note = f"Convergence criteria met: {new_critical} new Critical (≤{max_critical}), {new_major} new Major (≤{max_major})."
    elif round_num >= max_rounds:
        status = "HARD_LIMIT"
        hard_limit_action = convergence_config.get("hard_limit_action", "Report remaining issues.") if convergence_config else "Report remaining issues."
        note = f"Maximum {max_rounds} rounds reached. {hard_limit_action}"

    return {
        "status": status,
        "round": round_num,
        "max_rounds": max_rounds,
        "new_critical": new_critical,
        "new_major": new_major,
        "new_minor": new_minor,
        "prev_critical": prev_critical,
        "prev_major": prev_major,
        "degenerated": degenerated,
        "note": note,
    }


def detect_blockers(issues, blocker_ids):
    """Detect gate blockers from issue descriptions."""
    active_blockers = set()
    for issue in issues:
        if issue["severity"] == "Minor":
            continue
        desc = issue["description"].lower()
        for blocker_id in blocker_ids:
            keywords = BLOCKER_KEYWORDS.get(blocker_id, [])
            for kw in keywords:
                if kw.lower() in desc:
                    active_blockers.add(blocker_id)
                    break
    return sorted(active_blockers)


def load_calibration(calibration_path):
    """Load calibration YAML file."""
    if not calibration_path or not Path(calibration_path).exists():
        return None
    with open(calibration_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_calibration(score, calibration):
    """Apply additive calibration adjustment."""
    if calibration is None:
        return score, None
    adjustment = calibration.get("adjustment", {})
    adj_type = adjustment.get("type", "additive")
    adj_value = adjustment.get("value", 0)
    confidence = calibration.get("confidence", 0)
    if adj_type == "additive":
        adjusted = round(score + adj_value, 1)
    else:
        adjusted = score
    hint = {
        "applied": True,
        "source": calibration.get("source", "unknown"),
        "adjustment": adj_value,
        "confidence": confidence,
        "original_score": score,
        "adjusted_score": adjusted,
    }
    return adjusted, hint


def generate_report_md(tier, grade, total_score, dim_scores, blockers, issues, calibration_hint, depth_warnings=None,
                       confidence_data=None, agent_to_dim=None, variance_warnings=None):
    """Generate markdown report with optional confidence annotations."""
    # Build reverse mapping: dim_id -> first agent_id serving it
    dim_to_agent = {}
    if agent_to_dim:
        for agent_id, d_id in agent_to_dim.items():
            if d_id not in dim_to_agent:
                dim_to_agent[d_id] = agent_id

    # Collect variance warnings as set of dim_ids for quick lookup
    high_variance_dims = set()
    if variance_warnings:
        for w in variance_warnings:
            # Format: "agent_id: scores=..."
            agent_id = w.split(":")[0].strip()
            d_id = agent_to_dim.get(agent_id) if agent_to_dim else None
            if d_id:
                high_variance_dims.add(d_id)

    lines = [
        f"# 评审报告 — {tier}",
        f"",
        f"**等级：** {grade}",
        f"**总分：** {total_score}/100",
        f"",
        f"## 维度得分",
        f"",
        f"| 维度 | 得分 | 置信度 | 评价方式 |",
        f"|------|------|--------|----------|",
    ]
    for dim_id, score in sorted(dim_scores.items()):
        agent_id = dim_to_agent.get(dim_id)
        conf = confidence_data.get(agent_id) if confidence_data and agent_id else None
        confidence_str = f"{conf}/10" if conf is not None else "—"
        score_str = f"{score}" if score is not None else "N/A"
        if conf is not None and conf < LOW_CONFIDENCE_THRESHOLD:
            score_str = f"{score} [⚠ 低置信度]"
        # Determine method
        if dim_id == "ai_tone":
            method = "curves + agent"
        elif agent_id and variance_warnings and agent_id in "".join(str(v) for v in variance_warnings):
            method = "triplicate HIGH VARIANCE"
        elif agent_id and confidence_data and agent_id in confidence_data and confidence_data[agent_id] is not None:
            method = "triplicate"
        else:
            method = "single (定性)"
        lines.append(f"| {dim_id} | {score_str} | {confidence_str} | {method} |")

    if blockers:
        lines.extend([
            f"",
            f"## 阻塞项",
            f"",
        ])
        for b in blockers:
            lines.append(f"- **BLOCKER:** {b}")
        lines.append("")

    if calibration_hint and calibration_hint.get("applied"):
        lines.extend([
            f"",
            f"## 校准提示",
            f"",
            f"⚠️ 校准已应用：{calibration_hint['source']}",
            f"调整量：{calibration_hint['adjustment']:+.1f}（置信度：{calibration_hint['confidence']:.0%}）",
            f"原始得分：{calibration_hint['original_score']} → 校准后：{calibration_hint['adjusted_score']}",
            f"",
        ])

    critical = [i for i in issues if i["severity"] == "Critical"]
    major = [i for i in issues if i["severity"] == "Major"]
    minor = [i for i in issues if i["severity"] == "Minor"]

    if issues:
        lines.append(f"## 问题清单")
        lines.append(f"")
        if critical:
            lines.append(f"### Critical ({len(critical)})")
            for i, issue in enumerate(critical, 1):
                lines.append(f"{i}. [{issue['agent']}] {issue['description'][:100]}")
            lines.append("")
        if major:
            lines.append(f"### Major ({len(major)})")
            for i, issue in enumerate(major, 1):
                lines.append(f"{i}. [{issue['agent']}] {issue['description'][:100]}")
            lines.append("")
        if minor:
            lines.append(f"### Minor ({len(minor)})")
            for i, issue in enumerate(minor, 1):
                lines.append(f"{i}. [{issue['agent']}] {issue['description'][:100]}")
            lines.append("")

    if depth_warnings:
        lines.extend([
            f"",
            f"## 内容深度提醒",
            f"",
        ])
        for w in depth_warnings:
            lines.append(f"- [{w['type']}] {w['message']}")
        lines.append("")

    lines.append(f"---")
    lines.append(f"*Generated by evaluate/scoring.py on {date.today().isoformat()}*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate module scoring engine")
    parser.add_argument("--tier", required=True, choices=["course", "master", "humanities_bachelor", "stem_bachelor", "english_international"])
    parser.add_argument("--config-dir", required=True, help="Path to config/ directory")
    parser.add_argument("--agent-reports-dir", required=True, help="Path to agent report files")
    parser.add_argument("--output-dir", required=True, help="Where to write reports")
    parser.add_argument("--round", type=int, default=1, help="Review round number (1-3) for convergence tracking")
    parser.add_argument("--calibration", help="Path to calibration YAML file")
    parser.add_argument("--previous-report-dir", help="Previous evaluation output dir for re-audit")
    parser.add_argument("--paper-text", help="Path to paper plain text file for scripted AI detection")
    parser.add_argument("--discipline", choices=["general", "stem", "humanities"], default="general",
                        help="Discipline for curve inflection tuning (default: general)")
    parser.add_argument("--passport-state", help="Path to .pipeline_state.json for confidence ledger write-back")
    parser.add_argument("--evidence-grades", help="Path to evidence grades JSON for claim cross-referencing")
    args = parser.parse_args()

    config = load_config(args.config_dir, args.tier)
    dimensions = config["dimensions"]
    thresholds = config["grade_thresholds"]
    blocker_ids = config["gate_blockers"]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = Path(args.agent_reports_dir)

    # === Run text_stats early for deterministic AI marker counts ===
    script_stats = {}
    if args.paper_text:
        script_stats = run_text_stats(args.paper_text)
        if script_stats:
            print(f"  Text stats loaded: {script_stats.get('char_count', 0)} chars")

    # Parse each dimension's agent report
    dim_scores = {}
    all_issues = []
    used_agents = set()
    agent_to_dim = {}
    variance_warnings = []
    _median_report_paths = {}  # agent_id -> median run file path
    deep_pattern_findings = {}  # populated in ai_tone dim loop, read after
    _confidence_data = {}  # agent_id -> median_confidence
    _low_confidence_agents = []  # agents with median_confidence < threshold
    for dim in dimensions:
        for agent_id in dim["agents"]:
            used_agents.add(agent_id)
            agent_to_dim[agent_id] = dim["id"]

            # Triplicate scoring
            if dim["id"] == "ai_tone" or dim.get("scoreless"):
                # Scoreless dimension (ai_tone or factual_accuracy): agent is qualitative only.
                # Single run (not triplicate) — no score variance concern.
                median_score = None
                variance_high = False
                # ai_tone: collect deep patterns from all available runs
                _all_deep_patterns = {k: [] for k in DEEP_PATTERN_KEYS}
                median_path = None
                if dim.get("scoreless") and dim["id"] != "ai_tone":
                    # Non-ai_tone scoreless agent: single run
                    median_path = reports_dir / f"{agent_id}_review.md"
                else:
                    # ai_tone: triplicate, collect deep patterns
                    for i in range(1, 4):
                        p = reports_dir / f"{agent_id}_review_{i}.md"
                        if p.exists():
                            dp = parse_deep_patterns(str(p))
                            for k in DEEP_PATTERN_KEYS:
                                _all_deep_patterns[k].append(dp.get(k, False))
                            if median_path is None:
                                median_path = p
                    if median_path is None:
                        median_path = reports_dir / f"{agent_id}_review.md"
                # Median level for each deep pattern (sort by ordinal, pick middle value)
                deep_pattern_findings = {}
                for k in DEEP_PATTERN_KEYS:
                    votes = _all_deep_patterns[k]
                    if votes:
                        sorted_votes = sorted(votes, key=lambda v: LEVEL_ORDER.get(v, 0))
                        deep_pattern_findings[k] = sorted_votes[len(sorted_votes) // 2]
                    else:
                        deep_pattern_findings[k] = "none"
            else:
                median_score, variance_high, scores, median_confidence = parse_agent_scores_triplicate(reports_dir, agent_id)
                _confidence_data[agent_id] = median_confidence
                if median_confidence is not None and median_confidence < LOW_CONFIDENCE_THRESHOLD:
                    _low_confidence_agents.append(agent_id)
                dim_scores.setdefault(dim["id"], median_score)
                # Pick median run's file for issues
                median_idx = None
                if scores:
                    sorted_with_idx = sorted((s, i) for i, s in enumerate(scores))
                    median_idx = sorted_with_idx[len(sorted_with_idx) // 2][1]
                if variance_high:
                    warn = f"  VARIANCE WARNING: {agent_id} scores={scores}, range={max(scores)-min(scores):.0f} > threshold {VARIANCE_THRESHOLD}"
                    print(warn)
                    variance_warnings.append(warn)
                if median_idx is not None:
                    median_path = reports_dir / f"{agent_id}_review_{median_idx + 1}.md"
                else:
                    median_path = reports_dir / f"{agent_id}_review.md"
            _median_report_paths[agent_id] = median_path

            issues = parse_issues(str(median_path), agent_id, dim["id"])
            all_issues.extend(issues)

    # Report missing agents (check triplicate _1.md or single)
    for agent_id in used_agents:
        r1 = reports_dir / f"{agent_id}_review_1.md"
        single = reports_dir / f"{agent_id}_review.md"
        if not r1.exists() and not single.exists():
            print(f"WARNING: Agent report missing: {agent_id}_review.md (or _1.md)")

    # === v2 升级管线 ===

    # (三) 维度评分映射（创新基线等）
    ai_tone_for_mapping = dim_scores.get("ai_tone", 100)
    for dim in dimensions:
        mapping = dim.get("score_mapping")
        if mapping and dim["id"] in dim_scores and dim_scores[dim["id"]] is not None:
            min_ai = mapping.get("min_ai_tone", 0)
            if ai_tone_for_mapping >= min_ai:
                raw = dim_scores[dim["id"]]
                dim_scores[dim["id"]] = apply_score_mapping(raw, mapping)
                print(f"  Score mapping ({dim['id']}): {raw} -> {dim_scores[dim['id']]} (ai_tone={ai_tone_for_mapping})")
            else:
                print(f"  Score mapping ({dim['id']}): SKIPPED (ai_tone={ai_tone_for_mapping} < min={min_ai})")

    # (四) AI 关键词计数 + sigmoid 曲线 — 从text_stats获取确定性计数
    curves_config = config.get("ai_tone_curves")
    if curves_config:
        markers = {}
        if script_stats:
            char_count = script_stats.get("char_count", 0)
            markers = {
                "character": char_count,
                "benwen": script_stats.get("benwen_raw", 0),
                "gaix": script_stats.get("gaix_raw", 0),
                "danshi": script_stats.get("danshi_raw", 0),
                "suizhe": script_stats.get("suizhe_raw", 0),
                "ba": script_stats.get("ba_raw", 0),
                "jinxing": script_stats.get("jinxing_raw", 0),
                "yinci": script_stats.get("yinci_raw", 0),
                "tongguo": script_stats.get("tongguo_raw", 0),
                "em_dash": script_stats.get("em_dash_raw", 0),
                "paren_density": script_stats.get("paren_raw", 0),
                # Humanities-specific markers
                "gudian_narrative": script_stats.get("gudian_narrative_raw", 0),
                "shenghua": script_stats.get("shenghua_raw", 0),
                "duizhang_title": script_stats.get("duizhang_title_raw", 0),
                "kongdong": script_stats.get("kongdong_raw", 0),
                "meirong": script_stats.get("meirong_raw", 0),
                "first_person": script_stats.get("first_person_raw", 0),
                "uncertainty": script_stats.get("uncertainty_raw", 0),
                "counter_intuitive": script_stats.get("counter_intuitive_raw", 0),
                # STEM-specific markers
                "formulaic_conclusion": script_stats.get("formulaic_conclusion_raw", 0),
                "data_display_stencil": script_stats.get("data_display_stencil_raw", 0),
                "benyanjiu": script_stats.get("benyanjiu_raw", 0),
                "sequential_citations": script_stats.get("sequential_citations_raw", 0),
                "experimental_template": script_stats.get("experimental_template_raw", 0),
            }
        if markers.get("character", 0) > 0:
            curve_penalty = compute_ai_curve_penalty(markers, curves_config, args.discipline)
            ai_tone = max(0, 100 - curve_penalty)
            dim_scores["ai_tone"] = ai_tone
            disc_tag = f" ({args.discipline})" if args.discipline != "general" else ""
            print(f"  AI curves{disc_tag} (script counts): -{curve_penalty}, baseline=100 -> {ai_tone:.1f}")
            print(f"  AI markers (script): {markers}")
        elif dim_scores.get("ai_tone") is None:
            print(f"  WARNING: No text_stats available for AI curves, ai_tone=100 default")
            dim_scores["ai_tone"] = 100

    # (四点五) 深层模式扣分 — 章节同质化/摘要拼凑/讨论无深度/致谢模板
    # 这些是降AI也改不掉的结构性硬伤
    if deep_pattern_findings and dim_scores.get("ai_tone") is not None:
        deep_deduction, deep_details = deep_pattern_deduction(deep_pattern_findings)
        if deep_deduction > 0:
            current = dim_scores["ai_tone"]
            dim_scores["ai_tone"] = max(0, current - deep_deduction)
            detail = ", ".join(deep_details)
            print(f"  Deep pattern deduction: -{deep_deduction} ({detail}) from {current:.1f} -> {dim_scores['ai_tone']:.1f}")
        else:
            print(f"  Deep patterns: none found (clean)")

    # (三点五) 置信度融合 — 脚本检测器信号与曲线分融合
    fusion_config = config.get("ai_fusion")
    if fusion_config and args.paper_text and script_stats:
        agent_ai = dim_scores.get("ai_tone")
        if agent_ai is not None:
            original_ai = agent_ai
            dim_scores["ai_tone"] = fuse_ai_penalty(agent_ai, script_stats, fusion_config)
            print(f"  AI fusion: {original_ai:.1f} -> {dim_scores['ai_tone']:.1f}")

    # (三点五五) AI_MARKERS兜底: benwen密度<5/万字说明是手写, ai_tone不应<60
    # 条件: ①benwen密度<5 且 ②agent原始分非极端低(>=25) — 排除纯AI论文
    floor_markers = locals().get('markers') or {}
    if not floor_markers and curves_config:
        for agent_id, dim_id in agent_to_dim.items():
            if dim_id == "ai_tone":
                fp = _median_report_paths.get(agent_id, reports_dir / f"{agent_id}_review.md")
                floor_markers = parse_ai_markers(str(fp))
                break
    if floor_markers and dim_scores.get("ai_tone") is not None:
        benwen = floor_markers.get("benwen", 0)
        chars = floor_markers.get("character", 0) or floor_markers.get("character_count", 0)
        if chars > 0 and 0 <= benwen < 5 * (chars / 10000):
            current = dim_scores["ai_tone"]
            # Only pull up if agent+curves didn't already tank to extreme low (<25)
            if 25 <= current < 60:
                dim_scores["ai_tone"] = 60
                print(f"  AI marker floor applied: benwen={benwen}/{chars} (density {benwen/(chars/10000):.1f}/万字 < 5), agent+curves={current} -> 60")

    # (三点六) 论文长度评价 — 从text_stats获取字数，对论证质量维度施加修正
    char_count = script_stats.get("char_count", 0)
    if char_count > 0:
        length_mod, length_warning = evaluate_paper_length(char_count, config)
        if length_mod != 0:
            # Try argumentation_quality (STEM v2), then content (legacy), then any dimension
            target_dims = ["argumentation_quality", "content"]
            target = None
            for td in target_dims:
                if td in dim_scores and dim_scores[td] is not None:
                    target = td
                    break
            if target is None:
                # Fall back to first non-ai_tone scored dimension
                for dim in dimensions:
                    if dim["id"] != "ai_tone" and dim["id"] in dim_scores and dim_scores[dim["id"]] is not None:
                        target = dim["id"]
                        break
            if target is not None:
                old = dim_scores[target]
                dim_scores[target] = max(0, min(100, old + length_mod))
                print(f"  Paper length penalty: {length_mod} on {target} (was {old}, now {dim_scores[target]})")
                if length_warning:
                    print(f"  Length warning: {length_warning}")

    # (三点七) 内容深度客观测量 — advisory warnings, 不自动调整分数
    depth_warnings = []
    if args.paper_text:
        depth_result = run_content_depth(args.paper_text)
        depth_metrics = depth_result.get("metrics", {})
        if depth_metrics:
            content_score = dim_scores.get("content") or dim_scores.get("argumentation_quality")
            if content_score is not None:
                cv = depth_metrics.get("para_length_stats", {}).get("cv", 0)
                arg_density = depth_metrics.get("argument_marker_density", 0)
                avg_sents = depth_metrics.get("avg_sentences_per_para", 0)
                sb = depth_metrics.get("section_balance", {})
                if cv < 0.2:
                    depth_warnings.append({"type": "para_length_uniform", "message": f"段落长度变异系数过低({cv:.2f})，段落长度几乎一致"})
                if arg_density < 1.0:
                    depth_warnings.append({"type": "low_argument_density", "message": f"论点标记词密度过低({arg_density}次/万字)，论证结构可能不足"})
                if avg_sents < 2:
                    depth_warnings.append({"type": "short_paragraphs", "message": f"段落平均句数过低({avg_sents})"})
                elif avg_sents > 8:
                    depth_warnings.append({"type": "long_paragraphs", "message": f"段落平均句数过高({avg_sents})"})
                if content_score >= 75 and arg_density < 2.0:
                    depth_warnings.append({"type": "score_metric_divergence", "message": f"内容评分较高({content_score})但论点词密度偏低({arg_density}次/万字)"})
                if depth_warnings:
                    print(f"  Content depth warnings: {len(depth_warnings)}")
                    for w in depth_warnings:
                        print(f"    [{w['type']}] {w['message']}")

    # (一) 耦合规则：钳制 + 发散惩罚 + 动态权重
    coupling_rules = config.get("coupling_rules", [])
    dim_scores, final_weights = apply_coupling(dim_scores, coupling_rules, dimensions)

    # 用最终权重构造 adjusted dimensions
    adjusted_dimensions = []
    for dim in dimensions:
        adjusted = dict(dim)
        adjusted["weight"] = final_weights.get(dim["id"], dim["weight"])
        adjusted_dimensions.append(adjusted)
    dimensions = adjusted_dimensions

    # Compute score and grade
    total_score = compute_weighted_total(dim_scores, dimensions)
    grade = map_to_grade(total_score, thresholds)
    blockers = detect_blockers(all_issues, blocker_ids)

    # Apply calibration
    calibration = load_calibration(args.calibration)
    if calibration:
        adjusted_score, calibration_hint = apply_calibration(total_score, calibration)
        if calibration_hint and calibration_hint.get("applied"):
            grade = map_to_grade(adjusted_score, thresholds)
            total_score = adjusted_score

    # ── Convergence tracking ──
    convergence_config = config.get("convergence", {})
    prev_report_path = None
    if args.previous_report_dir:
        prev_report_path = Path(args.previous_report_dir) / "report.json"
    convergence = compute_convergence(
        all_issues, prev_report_path, convergence_config, args.round
    )
    print(f"  Convergence [{convergence['status']}]: R{args.round}/{convergence.get('max_rounds', 3)}, "
          f"new C={convergence.get('new_critical', '?')} M={convergence.get('new_major', '?')}")

    # Generate outputs
    report_md = generate_report_md(
        args.tier, grade, total_score, dim_scores,
        blockers, all_issues,
        calibration_hint if calibration else None,
        depth_warnings,
        confidence_data=_confidence_data,
        agent_to_dim=agent_to_dim,
        variance_warnings=variance_warnings,
    )

    # Append deep patterns and variance warnings to report
    dp_found = {k: v for k, v in deep_pattern_findings.items() if v and v != "none"}
    if dp_found:
        report_md += "\n\n## 深层AI模式\n\n"
        report_md += "以下结构性缺陷无法通过关键词替换修复，即使经过降AI处理仍会留下痕迹：\n\n"
        labels = {
            "homogeneity": "章节同质化",
            "abstract_patchwork": "摘要拼凑",
            "discussion_shallow": "讨论无深度",
            "acknowledgment_template": "致谢模板化",
        }
        level_zh = {"low": "轻度", "medium": "中等", "high": "重度", "severe": "严重"}
        for k, level in dp_found.items():
            label = labels.get(k, k)
            pmap = DEEP_PATTERN_LEVEL_MAP.get(k, {})
            penalty = pmap.get(level, 0)
            lzh = level_zh.get(level, level)
            report_md += f"- **{label}** — {lzh}（扣{penalty}分）\n"

    # Evidence grade claim cross-referencing
    low_evidence_claims = []
    if args.evidence_grades:
        eg_path = Path(args.evidence_grades)
        if eg_path.exists():
            try:
                raw = json.loads(eg_path.read_text(encoding="utf-8"))
                entries = raw if isinstance(raw, list) else raw.get("entries", [])
                grade_map = {}
                for entry in entries:
                    if isinstance(entry, dict):
                        sid = entry.get("source_id", "")
                        fg = entry.get("final_grade", "")
                        if sid and fg in ("LOW", "VERY_LOW"):
                            grade_map[sid] = fg
                for issue in all_issues:
                    desc = issue.get("description", "")
                    for sid, fg in grade_map.items():
                        if sid.lower() in desc.lower()[:200]:
                            low_evidence_claims.append({
                                "source_id": sid,
                                "final_grade": fg,
                                "claim": desc[:120],
                                "agent": issue.get("agent", "unknown"),
                            })
                            break
            except Exception as e:
                print(f"WARNING: evidence grade parsing failed: {e}")

    # Convergence status
    if convergence and convergence.get("status") != "first_round":
        status_labels = {
            "CONVERGED": "已收敛",
            "CONTINUE": "需要继续修改",
            "HARD_LIMIT": "已达轮次上限",
            "DEGENERATED": "退行警告 —— 已修复的问题复现",
        }
        status_label = status_labels.get(convergence["status"], convergence["status"])
        report_md += f"\n\n## 收敛状态 — {status_label}\n\n"
        report_md += f"- 当前轮次: R{convergence['round']}/{convergence.get('max_rounds', 3)}\n"
        report_md += f"- 本轮新 Critical: {convergence.get('new_critical', 0)}\n"
        report_md += f"- 本轮新 Major: {convergence.get('new_major', 0)}\n"
        report_md += f"- 本轮新 Minor: {convergence.get('new_minor', 0)}\n"
        if convergence.get("note"):
            report_md += f"- {convergence['note']}\n"
        if convergence["status"] == "CONVERGED":
            report_md += "\n评审已收敛。剩余问题为 Minor 级别，可选择性处理。\n"
        elif convergence["status"] == "HARD_LIMIT":
            report_md += "\n已到达最大评审轮次。剩余问题以 caveat 形式记录，建议人工判断是否继续修改。\n"
        elif convergence["status"] == "DEGENERATED":
            report_md += "\n**请停止迭代。** 修改方案可能需要重新设计。请人工审查退行的问题。\n"

    if low_evidence_claims:
        report_md += "\n\n## 证据等级标记\n\n"
        report_md += "以下发现依赖的证据等级较低（LOW/VERY_LOW），建议审慎对待：\n\n"
        for c in low_evidence_claims:
            report_md += f"- [{c['agent']}] 引用 {c['source_id']}（{c['final_grade']}）：{c['claim']}\n"

    report_json = {
        "tier": args.tier,
        "grade": grade,
        "total_score": total_score,
        "round": args.round,
        "dimension_scores": {k: v for k, v in dim_scores.items()},
        "blockers": blockers,
        "issues": all_issues,
        "calibration": calibration_hint if calibration else None,
        "convergence": convergence,
        "depth_warnings": depth_warnings,
        "variance_warnings": variance_warnings,
        "deep_patterns": {k: {"level": v, "penalty": DEEP_PATTERN_LEVEL_MAP.get(k, {}).get(v, 0)} for k, v in dp_found.items()},
        "confidence_data": {k: v for k, v in _confidence_data.items() if v is not None},
        "low_confidence_agents": _low_confidence_agents,
        "evidence_grade_flags": low_evidence_claims,
        "generated_at": date.today().isoformat(),
    }

    # Append low-confidence warnings to report
    if _low_confidence_agents:
        report_md += "\n\n## 低置信度警告\n\n"
        report_md += "以下 agent 的置信度较低（<5/10），建议人工复审：\n\n"
        for agent_id in _low_confidence_agents:
            conf = _confidence_data.get(agent_id, "N/A")
            dim_id = agent_to_dim.get(agent_id, "unknown")
            report_md += f"- **{agent_id}** ({dim_id}) — 置信度: {conf}/10 [⚠ 建议人工复审]\n"

    # Append variance warnings to report
    if variance_warnings:
        report_md += "\n\n## 评分稳定性警告\n\n"
        for w in variance_warnings:
            lines = w.split(", ")
            report_md += f"- {lines[0]}: {' | '.join(lines[1:])}\n"

    # Write report files
    with open(output_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    with open(output_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)

    print(f"Report generated: {output_dir / 'report.md'}")
    print(f"Data: {output_dir / 'report.json'}")
    print(f"Grade: {grade} (total: {total_score})")

    # Note: previous report copy stored for re-audit
    if args.previous_report_dir:
        prev_path = Path(args.previous_report_dir) / "report.json"
        if prev_path.exists():
            import shutil
            shutil.copy(str(prev_path), str(output_dir / "report_previous.json"))
            print("Previous report found. Re-audit diff can be generated with diff_issues.py")

    # ── 2B: Passport confidence ledger write-back ──
    if args.passport_state:
        passport_path = Path(args.passport_state)
        state = {}
        if passport_path.exists():
            try:
                state = json.loads(passport_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        try:
            if "passport" not in state:
                state["passport"] = {}
            if "confidence_ledger" not in state["passport"]:
                state["passport"]["confidence_ledger"] = []
            for agent_id, conf in _confidence_data.items():
                if conf is not None:
                    state["passport"]["confidence_ledger"].append({
                        "agent_id": agent_id,
                        "confidence_score": conf,
                        "timestamp": date.today().isoformat(),
                    })
            if _low_confidence_agents:
                if "unresolved_items" not in state:
                    state["unresolved_items"] = []
                for agent_id in _low_confidence_agents:
                    dim_id = agent_to_dim.get(agent_id, "unknown")
                    state["unresolved_items"].append({
                        "type": "low_confidence",
                        "agent_id": agent_id,
                        "dimension": dim_id,
                        "score": _confidence_data.get(agent_id, "N/A"),
                        "priority": "high",
                    })
            tmp_path = passport_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp_path.replace(passport_path)
            print(f"Passport confidence ledger updated: {passport_path}")
        except Exception as e:
            print(f"WARNING: passport write-back failed: {e}")


if __name__ == "__main__":
    main()
