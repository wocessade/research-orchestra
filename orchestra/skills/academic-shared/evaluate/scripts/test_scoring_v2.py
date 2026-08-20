"""Unit tests for scoring v2 — coupling, sigmoid, mapping, markers."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import *


def test_sigmoid():
    p = sigmoid_penalty(10, 25, 10, 0.3)
    assert 11 < p < 14, f"sigmoid(10) should be ~12.5, got {p}"
    p2 = sigmoid_penalty(0, 25, 10, 0.3)
    assert p2 < 2, f"sigmoid(0) should be near 0, got {p2}"
    print(f"  sigmoid PASS: f(10)={p:.1f}, f(0)={p2:.1f}")


def test_score_mapping():
    assert apply_score_mapping(0, {"floor": 40, "segments": [{"raw": [0, 20], "mapped": [40, 40]}]}) == 40
    assert apply_score_mapping(30, {"floor": 40, "segments": [{"raw": [20, 40], "mapped": [40, 65]}]}) == 52.5
    assert apply_score_mapping(50, {"floor": 40, "segments": [{"raw": [40, 60], "mapped": [65, 85]}]}) == 75.0
    assert apply_score_mapping(68, {"floor": 40, "segments": [{"raw": [60, 100], "mapped": [85, 100]}]}) == 88.0
    assert apply_score_mapping(None, None) is None
    assert apply_score_mapping(0, None) == 0
    print("  score_mapping PASS")


def test_clamp():
    # ai_tone=0 should clamp content and logic to 60
    scores = {"ai_tone": 0, "content": 70, "logic": 80}
    rules = [{"source": "ai_tone", "targets": ["content", "logic"], "type": "clamp_max",
              "zones": [{"ai_max": 40, "target_max": 60}, {"ai_max": 70, "target_max_offset": 20}]}]
    dims = [{"id": "ai_tone", "weight": 0.15}, {"id": "content", "weight": 0.25}, {"id": "logic", "weight": 0.20}]
    result, _ = apply_coupling(dict(scores), rules, dims)
    assert result["content"] == 60, f"content should be capped at 60, got {result['content']}"
    assert result["logic"] == 60, f"logic should be capped at 60, got {result['logic']}"

    # ai_tone=50 → target_max_offset = 50+20=70 cap
    scores2 = {"ai_tone": 50, "content": 85, "logic": 85}
    result2, _ = apply_coupling(scores2, rules, dims)
    assert result2["content"] == 70, f"content should be capped at 70 (50+20), got {result2['content']}"

    # ai_tone=85 → no zone matches, should NOT clamp
    scores3 = {"ai_tone": 85, "content": 90, "logic": 90}
    result3, _ = apply_coupling(scores3, rules, dims)
    assert result3["content"] == 90, f"content should NOT be clamped at ai_tone=85, got {result3['content']}"
    print("  clamp PASS")


def test_divergence():
    # format=88, content=35 → diff=53>25, content<60 → penalty = 53*0.3=15.9, capped at 10
    scores = {"format": 88, "content": 35, "ai_tone": 50, "logic": 50}
    rules = [{"sources": ["format", "content"], "type": "divergence_penalty",
              "condition": {"min_divergence": 25, "target_max_for_penalty": 60},
              "penalty_factor": 0.3, "max_penalty": 10, "target": "content"}]
    dims = [{"id": "format", "weight": 0.15}, {"id": "content", "weight": 0.25}]
    result, _ = apply_coupling(dict(scores), rules, dims)
    assert 25.0 <= result["content"] <= 25.1, f"content should be 35-10=25, got {result['content']}"

    # No divergence (南邮 pattern: format=82, content=78) → no penalty
    scores_ok = {"format": 82, "content": 78}
    result_ok, _ = apply_coupling(scores_ok, rules, dims)
    assert result_ok["content"] == 78, f"content should NOT be penalized (diff=4<25), got {result_ok['content']}"

    # diverges but content is high (>=60) → no penalty
    scores_hi = {"format": 90, "content": 65}
    result_hi, _ = apply_coupling(scores_hi, rules, dims)
    assert result_hi["content"] == 65, f"content should NOT be penalized (content=65>=60), got {result_hi['content']}"
    print("  divergence PASS")


def test_dynamic_weight():
    # ai_tone=80, innovation=75 → weight=0.20, borrow from content/structure
    scores = {"ai_tone": 80, "innovation": 75}
    rules = [{"sources": ["ai_tone", "innovation"], "target": "innovation", "type": "dynamic_weight",
              "default_weight": 0.10,
              "mapping": [{"condition": "ai_tone >= 70 && innovation >= 70", "weight": 0.20,
                           "borrow_from": {"content": -0.05, "structure": -0.05}}]}]
    dims = [{"id": "ai_tone", "weight": 0.15}, {"id": "innovation", "weight": 0.10},
            {"id": "content", "weight": 0.25}, {"id": "structure", "weight": 0.15}]
    _, weights = apply_coupling(dict(scores), rules, dims)
    assert abs(weights["innovation"] - 0.20) < 0.001, f"innov weight should be 0.20, got {weights['innovation']}"
    assert abs(weights["content"] - 0.20) < 0.001, f"content weight should be 0.20 (0.25-0.05), got {weights['content']}"
    assert abs(weights["structure"] - 0.10) < 0.001, f"structure weight should be 0.10 (0.15-0.05), got {weights['structure']}"

    # ai_tone=30 → weight=0.05, give to format/structure
    scores_ai = {"ai_tone": 30, "innovation": 75}
    rules2 = [{"sources": ["ai_tone", "innovation"], "target": "innovation", "type": "dynamic_weight",
               "default_weight": 0.10,
               "mapping": [{"condition": "ai_tone < 50", "weight": 0.05,
                            "give_to": {"format": 0.03, "structure": 0.02}}]}]
    dims2 = [{"id": "ai_tone", "weight": 0.15}, {"id": "innovation", "weight": 0.10},
             {"id": "format", "weight": 0.15}, {"id": "structure", "weight": 0.15}]
    _, weights2 = apply_coupling(dict(scores_ai), rules2, dims2)
    assert abs(weights2["innovation"] - 0.05) < 0.001, f"innov weight should be 0.05 for ai_tone<50, got {weights2['innovation']}"
    assert abs(weights2["format"] - 0.18) < 0.001, f"format weight should be 0.18 (0.15+0.03), got {weights2['format']}"

    # No matching condition → default_weight should be used
    scores_def = {"ai_tone": 60, "innovation": 65}
    _, weights3 = apply_coupling(scores_def, rules2, dims2)
    assert abs(weights3["innovation"] - 0.10) < 0.001, f"innov weight should use default 0.10, got {weights3['innovation']}"
    print("  dynamic_weight PASS")


def test_eval_condition():
    assert eval_condition("ai_tone >= 70 && innovation >= 70", 80, 75) is True
    assert eval_condition("ai_tone >= 70 && innovation >= 70", 80, 65) is False
    assert eval_condition("ai_tone < 50", 30, 0) is True
    assert eval_condition("ai_tone >= 50", 60, 0) is True
    assert eval_condition("ai_tone < 40", 50, 0) is False
    # Invalid condition should return False (failsafe)
    assert eval_condition("xzy_bad_syntax", 80, 75) is False
    print("  eval_condition PASS")


def test_ai_markers_parsing():
    """Test AI_MARKERS regex on a simulated report fragment."""
    content = """Some review text...
DIMENSION_SCORE: 45
AI_MARKERS:
  benwen_count: 29
  gaix_count: 27
  danshi_count: 18
  suizhe_count: 4
"""
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    markers = parse_ai_markers(tmp.name)
    os.unlink(tmp.name)
    assert markers.get("benwen") == 29, f"benwen should be 29, got {markers.get('benwen')}"
    assert markers.get("gaix") == 27
    assert markers.get("danshi") == 18
    assert markers.get("suizhe") == 4
    print(f"  AI_MARKERS parsing PASS: {markers}")


def test_compute_penalty():
    markers = {"benwen": 29, "gaix": 27, "danshi": 18, "suizhe": 4}
    curves = {
        "benwen": {"weight": 25, "curve": "sigmoid", "inflection": 10, "steepness": 0.3},
        "gaix": {"weight": 10, "curve": "sigmoid", "inflection": 12, "steepness": 0.25},
        "danshi": {"weight": 8, "curve": "sigmoid", "inflection": 8, "steepness": 0.3},
        "suizhe": {"weight": 8, "curve": "sigmoid", "inflection": 3, "steepness": 0.5},
    }
    penalty = compute_ai_curve_penalty(markers, curves)
    # 本文29: ~25, 该X27: ~10, 但是18: ~8, 随着4: ~6.5, total ~49-50
    assert 45 < penalty < 55, f"total penalty should be ~49, got {penalty}"
    print(f"  compute_penalty PASS: total={penalty}")
    # No markers near-zero penalty (sigmoid at density=0 with inflection>0 gives small positive)
    zero_penalty = compute_ai_curve_penalty({"character": 10000, "benwen": 0}, curves)
    assert 0 < zero_penalty < 10, f"zero-marker penalty should be small, got {zero_penalty}"
    print("  zero penalty PASS")


test_sigmoid()
test_score_mapping()
test_clamp()
test_divergence()
test_dynamic_weight()
test_eval_condition()
test_ai_markers_parsing()
test_compute_penalty()
print("\n=== ALL TESTS PASS ===")
