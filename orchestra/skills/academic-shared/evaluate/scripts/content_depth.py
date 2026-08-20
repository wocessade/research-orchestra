#!/usr/bin/env python3
"""content_depth.py — Objective content depth measurement.

Computes structural and stylistic metrics to cross-validate agent-based
content scoring. Output is advisory — warnings are generated when agent
scores deviate significantly from objective metrics, but no automatic
score adjustment is made.

Usage:
    python content_depth.py <paper.txt>
    python content_depth.py <paper.txt> --json  # default
"""

import json
import math
import re
import sys

# Paragraph boundary: one or more blank lines
PARA_SPLIT = re.compile(r'\n\s*\n')

# Sentence boundaries for Chinese text
SENTENCE_SPLIT = re.compile(r'[。！？\n]+')

# Argument markers: transition/argumentative words in Chinese academic writing
ARGUMENT_MARKERS = re.compile(
    r'因此|然而|但是|而且|此外|总之|综上所述|由此可见|'
    r'换言之|进一步|更重要的是|值得注意|一方面|另一方面|'
    r'尽管如此|基于此|由此可知|也就是说|具体而言|总体而言'
)

# Section heading heuristics
SECTION_HEADING = re.compile(r'^第[一二三四五六七八九十\d]+[章节部分]|^(摘要|引言|绪论|文献综述|'
                             r'研究方法|结果|讨论|结论|参考文献|致谢|附录|'
                             r'Abstract|Introduction|Method|Result|Discussion|Conclusion)',
                             re.MULTILINE)


def compute_content_depth(text: str) -> dict:
    """Compute content depth metrics from plain text.

    Returns dict with paragraph stats, citation density, argument marker
    density, section balance, and avg sentences per paragraph.
    """
    char_count = len(text)

    # Paragraph-level stats
    paras = [p.strip() for p in PARA_SPLIT.split(text) if p.strip()]
    para_count = len(paras)
    para_lengths = [len(p) for p in paras] if paras else [char_count]

    mean_pl = sum(para_lengths) / len(para_lengths)
    variance = sum((l - mean_pl) ** 2 for l in para_lengths) / len(para_lengths)
    std_pl = math.sqrt(variance)
    cv_pl = round(std_pl / mean_pl, 3) if mean_pl > 0 else 0

    # Sentence-level stats
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    sent_count = len(sentences)
    avg_sent_per_para = round(sent_count / para_count, 1) if para_count > 0 else 0

    # Argument marker density
    arg_markers = ARGUMENT_MARKERS.findall(text)
    norm = char_count / 10000 if char_count > 0 else 1.0
    arg_density = round(len(arg_markers) / norm, 2)

    # Section balance — estimate section boundaries from heading patterns
    heading_matches = list(SECTION_HEADING.finditer(text))
    if len(heading_matches) >= 3:
        intro_end = heading_matches[1].start()
        # Estimate: first section = intro, last section = conclusion
        conclusion_start = heading_matches[-1].start()
        intro_ratio = round(intro_end / char_count, 3) if char_count > 0 else 0
        body_ratio = round((conclusion_start - intro_end) / char_count, 3) if char_count > 0 else 0
        conclusion_ratio = round((char_count - conclusion_start) / char_count, 3) if char_count > 0 else 0
    else:
        # Fallback: split into thirds
        third = char_count / 3
        intro_ratio = round(third / char_count, 3) if char_count > 0 else 0
        body_ratio = round(third / char_count, 3) if char_count > 0 else 0
        conclusion_ratio = round(third / char_count, 3) if char_count > 0 else 0

    return {
        "char_count": char_count,
        "para_count": para_count,
        "para_length_stats": {
            "mean": round(mean_pl, 1),
            "std": round(std_pl, 1),
            "cv": cv_pl,
        },
        "avg_sentences_per_para": avg_sent_per_para,
        "sentence_count": sent_count,
        "argument_marker_density": arg_density,
        "section_balance": {
            "intro": intro_ratio,
            "body": body_ratio,
            "conclusion": conclusion_ratio,
        },
    }


def assess_content_depth_warnings(depth_metrics: dict, agent_content_score: float) -> list:
    """Generate advisory warnings when objective metrics diverge from agent score."""
    warnings = []

    cv = depth_metrics.get("para_length_stats", {}).get("cv", 0)
    if cv < 0.2:
        warnings.append({
            "type": "para_length_uniform",
            "severity": "info",
            "message": f"段落长度变异系数过低({cv:.2f})，所有段落长度几乎一致，可能是AI生成模式",
        })

    arg_density = depth_metrics.get("argument_marker_density", 0)
    if arg_density < 1.0:
        warnings.append({
            "type": "low_argument_density",
            "severity": "minor",
            "message": f"论点标记词密度过低({arg_density}次/万字)，论证结构可能不足",
        })

    avg_sents = depth_metrics.get("avg_sentences_per_para", 0)
    if avg_sents < 2:
        warnings.append({
            "type": "short_paragraphs",
            "severity": "info",
            "message": f"段落平均句数过低({avg_sents})，段落过短可能缺乏论证深度",
        })
    elif avg_sents > 8:
        warnings.append({
            "type": "long_paragraphs",
            "severity": "info",
            "message": f"段落平均句数过高({avg_sents})，段落过长不利于阅读",
        })

    sb = depth_metrics.get("section_balance", {})
    intro_ratio = sb.get("intro", 0)
    conclusion_ratio = sb.get("conclusion", 0)

    if agent_content_score >= 75:
        if arg_density < 2.0:
            warnings.append({
                "type": "score_metric_divergence",
                "severity": "minor",
                "message": f"内容评分较高({agent_content_score})但论点标记词密度偏低({arg_density}次/万字)，建议核查评分是否合理",
            })

    return warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: python content_depth.py <paper.txt>", file=sys.stderr)
        sys.exit(1)

    text_path = sys.argv[1]
    with open(text_path, encoding="utf-8") as f:
        text = f.read()

    metrics = compute_content_depth(text)
    output = {"metrics": metrics, "warnings": []}

    # Optionally add warnings
    # (Caller provides agent_score separately)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
