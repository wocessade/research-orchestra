#!/usr/bin/env python3
"""text_stats.py — Scripted statistical feature extraction for 降AI fingerprint detection.

Computes density of known 降AI tool artifacts per 10K characters:
- 把字句 density (ba_density)
- 进行/予以/加以 light verb density (jinxing_density)
- 该+N demonstrative density (gai_dingzhi_density)
- 被字句 density (bei_density)
- 所字结构 density (suo_density)
- 于字短语 density (yu_density)
- Citation density (citation_density)

Usage:
    python text_stats.py <paper.txt>
    python text_stats.py <paper.txt> --json  # default, output raw JSON
"""

import json
import re
import sys


# 把字句: "把 + object + verb" construction
BA_PATTERN = re.compile(r'把[^，。；：、！？\s]{1,8}')

# 轻动词: 进行/予以/加以 (formal/verbose verbs used to pad AI text)
JINXING_PATTERN = re.compile(r'进行|予以|加以')

# 该+N 定指: 该 followed by noun (demonstrative "the said" usage)
GAI_DINGZHI_PATTERN = re.compile(r'该[^，。；：、！？\s]{1,4}')

# 被字句: "被 + agent + verb" passive construction
BEI_PATTERN = re.compile(r'被[^，。；：、！？\s]{1,8}')

# 所字结构: 被/为...所... construction (formal passive)
SUO_PATTERN = re.compile(r'[被为].{0,8}所\w')

# 于字短语: verb + 于 structure (在于/关于/对于/由于/基于/源于等)
YU_PATTERN = re.compile(r'[一-鿿]于(?!是)')

# Citation markers: [1], [1,2], [1-3], (Author, year)
CITATION_PATTERN = re.compile(r'\[\d+(?:[,\-]\d+)*\]|\([^)]+?\d{4}[^)]*\)')

# 在+N+中/上/下: 方位框架句 — AI最强单一信号
ZAI_CONSTRUCTION_PATTERN = re.compile(r'在[一-鿿]{1,20}[中上下]')

# 通过+Verb: AI万能框架
TONGGUO_PATTERN = re.compile(r'通过[一-鿿]{1,10}')

# 不仅...也/还/而且: AI关联词套叠
BUJIN_PATTERN = re.compile(r'不仅')

# 从+X视角/角度/来看: AI经典转场
CONG_PERSPECTIVE_PATTERN = re.compile(r'从[一-鿿]{1,15}(?:视角|角度|层面|维度|来看)')

# 具有+抽象名词: AI空洞赞美词
JUYOU_PATTERN = re.compile(r'具有')

# 从而/进而: AI因果链过渡
CONGER_PATTERN = re.compile(r'从而|进而')

# 因此/故此: AI因果结论
YINCI_PATTERN = re.compile(r'因此|故此')

# 成为+载体/媒介/方式: AI抽象名词模式
CHENGWEI_PATTERN = re.compile(r'成为[一-鿿]{1,15}(?:载体|媒介|方式|途径|手段|体现|表现)')

# 本文 keyword — AI自指过度使用
BENWEN_PATTERN = re.compile(r'本文')

# 但是/但 — 转折词频率衡量AI节奏
DANSHI_PATTERN = re.compile(r'但是|但(?!是)')

# 随着...的发展 — AI模板句式
SUIZHE_PATTERN = re.compile(r'随着[^。；！？]{1,30}的发展')

# 破折号 —— overuse (Chinese em dash pair)
EM_DASH_PATTERN = re.compile(r'——')

# 中文括号 （） density — overuse indicator
PAREN_PATTERN = re.compile(r'（[^）]*）')

# ── Humanities-specific AI signal patterns ──

# 宏大叙事模式: "从古至今""纵观历史""千百年来""自古以来"
GUDIAN_NARRATIVE_PATTERN = re.compile(
    r'从古至今|纵观历史|千百年来|自古以来|'
    r'在漫长的历史|随着时代的变迁|纵观古今'
)

# 升华句式: AI段落结尾拔高模式
SHENGHUA_PATTERN = re.compile(
    r'不仅.{1,20}更是|'
    r'这深刻揭示了|'
    r'从本质上说|'
    r'具有深远|'
    r'为.{1,15}提供了新的视角|'
    r'由此可见.{1,10}(?:意义|价值)'
)

# 对仗式标题: 标题中的冒号对仗 (counted per heading)
DUIZHANG_TITLE_PATTERN = re.compile(r'^.{2,20}[与和的].{2,20}[：:].{2,30}$', re.MULTILINE)

# 空洞学术词: 深刻/深层/本质/内在逻辑
KONGDONG_PATTERN = re.compile(r'深刻|深层|本质|内在逻辑|深层结构|内在机制|根本性')

# 美式学术模板转场
MEIRONG_PATTERN = re.compile(
    r'从[一-鿿]{1,15}(?:视角|角度|层面|维度)(?:来看|出发|审视)|'
    r'在[一-鿿]{1,15}的框架下|'
    r'以[一-鿿]{1,15}(?:为切入点|为视角)'
)

# 第一人称体验 (人类写作信号)
FIRST_PERSON_PATTERN = re.compile(
    r'我认为|初读时|印象深刻的|我注意到|'
    r'笔者在阅读|翻阅.{1,10}时|'
    r'让笔者'
)

# 不确定性表达 (学术hedging)
UNCERTAINTY_PATTERN = re.compile(r'或许|可能|似乎|某种程度上|未必|不见得|难以断言')

# 反直觉判断 (人文洞察信号)
COUNTER_INTUITIVE_PATTERN = re.compile(
    r'表面上看.{1,30}实际上|'
    r'乍看之下.{1,30}然而|'
    r'不同于通常认为|'
    r'看似.{1,20}实则'
)

# 句首"该"字 (比STEM更敏感: 人文学科几乎不用该X)
GAI_SENTENCE_START_PATTERN = re.compile(r'(?:^|[。！？])\s*该[一-鿿]')

# ── STEM-specific AI signal patterns ──

# 公式化结论: "得出以下结论""主要结论如下"等AI论文标准结尾模板
FORMULAIC_CONCLUSION_PATTERN = re.compile(
    r'得出以下结论|主要结论如下|'
    r'综上所述.{0,5}本研究|'
    r'通过(?:上述|以上).{0,10}(?:分析|研究|实验).{0,5}(?:得出|得到|可以(?:看出|得出))'
)

# 数据展示模板: "从表X可以看出""如图X所示""表X展示了"等机械数据叙述
DATA_DISPLAY_STENCIL_PATTERN = re.compile(
    r'从(?:表|图|Table|Fig(?:ure)?)s?\d+.{0,5}(?:可以)?(?:看出|发现|观察到|得知)|'
    r'如(?:表|图)s?\d+.{0,3}所示|'
    r'(?:表|图)s?\d+.{0,5}(?:展示|呈现|显示)了'
)

# 本研究: AI自指高频词(STEM变体)
BENYANJIU_PATTERN = re.compile(r'本研究')

# 密集引用聚类: "[1,2,3]"或"[1][2]"连续引用而不区分贡献
SEQUENTIAL_CITATIONS_PATTERN = re.compile(
    r'\[\d+(?:[,，]\s*\d+){2,}\]|'   # [1,2,3] or [1,2,3,4]
    r'\[\d+\]\[\d+'                    # [1][2] adjacent
)

# 实验目的陈述模板: "为了验证...本研究设计了..."
EXPERIMENTAL_TEMPLATE_PATTERN = re.compile(
    r'为了验证.{0,30}(?:本研究|本文).{0,10}(?:设计|采用|构建|提出)了'
)

# Paragraph boundary (one or more blank lines)
PARA_SPLIT = re.compile(r'\n\s*\n')


def compute_text_stats(text: str) -> dict:
    """Compute text statistics from plain text content.

    Returns dict with raw counts and per-10K-char densities.
    """
    char_count = len(text)

    ba_raw = len(BA_PATTERN.findall(text))
    jinxing_raw = len(JINXING_PATTERN.findall(text))
    gai_raw = len(GAI_DINGZHI_PATTERN.findall(text))
    bei_raw = len(BEI_PATTERN.findall(text))
    suo_raw = len(SUO_PATTERN.findall(text))
    yu_raw = len(YU_PATTERN.findall(text))
    citation_raw = len(CITATION_PATTERN.findall(text))
    zai_construction_raw = len(ZAI_CONSTRUCTION_PATTERN.findall(text))
    tongguo_raw = len(TONGGUO_PATTERN.findall(text))
    bujin_raw = len(BUJIN_PATTERN.findall(text))
    cong_perspective_raw = len(CONG_PERSPECTIVE_PATTERN.findall(text))
    juyou_raw = len(JUYOU_PATTERN.findall(text))
    conger_raw = len(CONGER_PATTERN.findall(text))
    yinci_raw = len(YINCI_PATTERN.findall(text))
    chengwei_raw = len(CHENGWEI_PATTERN.findall(text))
    benwen_raw = len(BENWEN_PATTERN.findall(text))
    danshi_raw = len(DANSHI_PATTERN.findall(text))
    suizhe_raw = len(SUIZHE_PATTERN.findall(text))
    em_dash_raw = len(EM_DASH_PATTERN.findall(text))
    paren_raw = len(PAREN_PATTERN.findall(text))

    # ── Humanities-specific counts ──
    gudian_narrative_raw = len(GUDIAN_NARRATIVE_PATTERN.findall(text))
    shenghua_raw = len(SHENGHUA_PATTERN.findall(text))
    duizhang_title_raw = len(DUIZHANG_TITLE_PATTERN.findall(text))
    kongdong_raw = len(KONGDONG_PATTERN.findall(text))
    meirong_raw = len(MEIRONG_PATTERN.findall(text))
    first_person_raw = len(FIRST_PERSON_PATTERN.findall(text))
    uncertainty_raw = len(UNCERTAINTY_PATTERN.findall(text))
    counter_intuitive_raw = len(COUNTER_INTUITIVE_PATTERN.findall(text))
    gai_sentence_start_raw = len(GAI_SENTENCE_START_PATTERN.findall(text))

    # ── STEM-specific counts ──
    formulaic_conclusion_raw = len(FORMULAIC_CONCLUSION_PATTERN.findall(text))
    data_display_stencil_raw = len(DATA_DISPLAY_STENCIL_PATTERN.findall(text))
    benyanjiu_raw = len(BENYANJIU_PATTERN.findall(text))
    sequential_citations_raw = len(SEQUENTIAL_CITATIONS_PATTERN.findall(text))
    experimental_template_raw = len(EXPERIMENTAL_TEMPLATE_PATTERN.findall(text))

    paras = [p.strip() for p in PARA_SPLIT.split(text) if p.strip()]
    para_count = len(paras) if paras else 1

    # Convert to per-10K-char density
    norm = char_count / 10000 if char_count > 0 else 1.0

    return {
        "char_count": char_count,
        "para_count": para_count,
        "ba_density": round(ba_raw / norm, 2),
        "jinxing_density": round(jinxing_raw / norm, 2),
        "gai_dingzhi_density": round(gai_raw / norm, 2),
        "bei_density": round(bei_raw / norm, 2),
        "suo_density": round(suo_raw / norm, 2),
        "yu_density": round(yu_raw / norm, 2),
        "citation_density": round(citation_raw / norm, 2),
        "zai_construction_density": round(zai_construction_raw / norm, 2),
        "tongguo_density": round(tongguo_raw / norm, 2),
        "bujin_density": round(bujin_raw / norm, 2),
        "cong_perspective_density": round(cong_perspective_raw / norm, 2),
        "juyou_density": round(juyou_raw / norm, 2),
        "conger_density": round(conger_raw / norm, 2),
        "yinci_density": round(yinci_raw / norm, 2),
        "chengwei_density": round(chengwei_raw / norm, 2),
        "em_dash_density": round(em_dash_raw / norm, 2),
        "paren_density": round(paren_raw / norm, 2),
        # Humanities-specific densities
        "gudian_narrative_density": round(gudian_narrative_raw / norm, 2),
        "shenghua_density": round(shenghua_raw / norm, 2),
        "duizhang_title_raw": duizhang_title_raw,
        "kongdong_density": round(kongdong_raw / norm, 2),
        "meirong_density": round(meirong_raw / norm, 2),
        "first_person_density": round(first_person_raw / norm, 2),
        "uncertainty_density": round(uncertainty_raw / norm, 2),
        "counter_intuitive_density": round(counter_intuitive_raw / norm, 2),
        "gai_sentence_start_density": round(gai_sentence_start_raw / norm, 2),
        # STEM-specific densities
        "formulaic_conclusion_density": round(formulaic_conclusion_raw / norm, 2),
        "data_display_stencil_density": round(data_display_stencil_raw / norm, 2),
        "benyanjiu_density": round(benyanjiu_raw / norm, 2),
        "sequential_citations_density": round(sequential_citations_raw / norm, 2),
        "experimental_template_density": round(experimental_template_raw / norm, 2),
        # Raw counts for AI-tone curves (normalized by char_count in scoring.py)
        "benwen_raw": benwen_raw,
        "gaix_raw": gai_raw,
        "danshi_raw": danshi_raw,
        "suizhe_raw": suizhe_raw,
        "ba_raw": ba_raw,
        "jinxing_raw": jinxing_raw,
        "yinci_raw": yinci_raw,
        "tongguo_raw": tongguo_raw,
        # Humanities-specific raw counts
        "gudian_narrative_raw": gudian_narrative_raw,
        "shenghua_raw": shenghua_raw,
        "kongdong_raw": kongdong_raw,
        "meirong_raw": meirong_raw,
        "first_person_raw": first_person_raw,
        "uncertainty_raw": uncertainty_raw,
        "counter_intuitive_raw": counter_intuitive_raw,
        # STEM-specific raw counts
        "formulaic_conclusion_raw": formulaic_conclusion_raw,
        "data_display_stencil_raw": data_display_stencil_raw,
        "benyanjiu_raw": benyanjiu_raw,
        "sequential_citations_raw": sequential_citations_raw,
        "experimental_template_raw": experimental_template_raw,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python text_stats.py <paper.txt>", file=sys.stderr)
        sys.exit(1)

    text_path = sys.argv[1]
    with open(text_path, encoding="utf-8") as f:
        text = f.read()

    stats = compute_text_stats(text)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
