#!/usr/bin/env python3
"""
Regression tests for scoring.py bugs found in the Layer 4 audit.

Run:
    cd skills/academic-shared
    python evaluate/scripts/test_scoring_regression.py

Covers 6 regression scenarios from the 2-round multi-agent audit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import (
    CONFIDENCE_SCORE_RE,
    DIMENSION_SCORE_RE,
    compute_ai_curve_penalty,
)

PASS = lambda name: print(f"  {name} PASS")
FAIL = lambda name, msg: print(f"  {name} FAIL: {msg}")


def test_em_dash_raw_not_double_normalized():
    """compute_ai_curve_penalty must use raw count, not pre-normalized density.

    30 em-dashes in 20K chars → density = 15 per 10K chars.
    Old bug passed em_dash_density (already normalized) which got re-normalized,
    producing density=7.5 when char_count != 10000.
    """
    markers = {"character": 20000, "em_dash": 30}
    curves = {"em_dash": {"weight": 10, "curve": "sigmoid", "inflection": 10, "steepness": 0.3}}
    penalty = compute_ai_curve_penalty(markers, curves, "general")
    # density=15 with inflection=10: sigmoid gives substantial penalty
    assert penalty > 5, f"Expected >5 for 30em-dash/20Kchars, got {penalty}"
    PASS("test_em_dash_raw_not_double_normalized")


def test_paren_raw_not_double_normalized():
    """Same double-normalization check for paren_raw."""
    markers = {"character": 20000, "paren_density": 120}
    curves = {"paren_density": {"weight": 8, "curve": "sigmoid", "inflection": 60, "steepness": 0.25}}
    penalty = compute_ai_curve_penalty(markers, curves, "general")
    # density=60 with inflection=60 → ~50% of weight = ~4
    assert penalty > 2, f"Expected >2 for 120parens/20Kchars, got {penalty}"
    PASS("test_paren_raw_not_double_normalized")


def test_confidence_decimal_parsing():
    """CONFIDENCE_SCORE_RE must support decimals and variable spacing."""
    cases = [
        ("CONFIDENCE_SCORE: 7.5\nDIMENSION_SCORE: 80", 7.5),
        ("CONFIDENCE_SCORE: 10", 10.0),
        ("CONFIDENCE_SCORE : 3", 3.0),
        ("CONFIDENCE_SCORE: 5\nDIMENSION_SCORE: 78", 5.0),
        ("Text\nCONFIDENCE_SCORE: 4.2\nEnd", 4.2),
    ]
    for text, expected in cases:
        m = CONFIDENCE_SCORE_RE.search(text)
        assert m is not None, f"No match: {text!r}"
        assert float(m.group(1)) == expected, f"{text!r}: expected {expected}, got {m.group(1)}"
    PASS("test_confidence_decimal_parsing")


def test_dimension_score_decimal_parsing():
    """DIMENSION_SCORE_RE must handle decimals and dimension-specific prefix."""
    cases = [
        ("DIMENSION_SCORE: 78.5", 78.5),
        ("DIMENSION_SCORE: 100", 100.0),
        ("DIMENSION_SCORE content_quality: 82", 82.0),
        ("DIMENSION_SCORE ai_tone: 45.3", 45.3),
    ]
    for text, expected in cases:
        m = DIMENSION_SCORE_RE.search(text)
        assert m is not None, f"No match: {text!r}"
        assert float(m.group(1)) == expected, f"{text!r}: expected {expected}, got {m.group(1)}"
    PASS("test_dimension_score_decimal_parsing")


def test_bachelor_tier_rejected():
    """--tier bachelor must be rejected by argparse (removed in audit)."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=["course", "master", "humanities_bachelor", "stem_bachelor", "english_international"])
    try:
        parser.parse_args(["--tier", "bachelor"])
        FAIL("test_bachelor_tier_rejected", "argparse accepted invalid tier 'bachelor'")
    except SystemExit:
        PASS("test_bachelor_tier_rejected")


def test_cond_s12_not_in_dep_graph():
    """No dependency graph variant should contain 'cond_S12' (removed)."""
    import yaml
    manifest_path = Path(__file__).resolve().parent.parent.parent / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    dep_graph = manifest.get("dependency_graph", {})
    for gname, gstages in dep_graph.items():
        flat = []
        for gs in gstages:
            if isinstance(gs, list):
                flat.extend(gs)
            else:
                flat.append(gs)
        for gs in flat:
            assert "cond_S12" not in (gs or ""), f"dep_graph '{gname}' contains 'cond_S12' (removed)"
    PASS("test_cond_s12_not_in_dep_graph")


if __name__ == "__main__":
    print("scoring.py regression tests:")
    tests = [
        test_em_dash_raw_not_double_normalized,
        test_paren_raw_not_double_normalized,
        test_confidence_decimal_parsing,
        test_dimension_score_decimal_parsing,
        test_bachelor_tier_rejected,
        test_cond_s12_not_in_dep_graph,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  {t.__name__} FAIL: {e}")
            failed += 1
    print(f"\n{passed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
