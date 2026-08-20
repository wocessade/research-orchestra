"""
论文一键注水工具 v4 — 写作风格扰动引擎

用法:
  python inflate_paper.py input.docx [options]

选项:
  --intensity {light|medium|heavy|ultra}    注水强度 (默认 medium)
  --output OUTPUT                           输出路径
  --dry-run                                 只打印统计，不改写
  --stats                                   打印变换前后的文本统计特征
  --aigc-flags FILE                         AIGC 标红片段 txt，仅注水匹配段落

强度挡位:
  light    轻微扰动，保留原貌，适合终稿微调
  medium   中等注水，平衡质与量 (已验证 64%→33% AIGC)
  heavy    充分注水，优先降检测率
  ultra    极端注水，允许一定的语言冗余换取最大字数

变换管线 (依次执行，每段最多命中 N 次):
  1. [DE-AI]    删除AI高频连接词，打断模板化结构
  2. [缩写]     缩写展开 (电子鼻 → Electronic Nose)
  3. [冗余]     判断句加冗余 (是→可以说是)
  4. [口语化]   AI学术套话→真人表达变体 (实验结果表明→从实验数据来看)
  5. [同义改写]  句式级改写 (A导致B→B与A密切相关)
  6. [句首]     句首插入废话/连接词
  7. [不对称]   打破对称结构 (不仅A而且B→不对称展开)
  8. [主语]     主语抽象化 (这→这一现象)
  9. [被动]     变主动为被动 (推动了→起到推动作用)
  10.[语序]     语序颠倒 (因为A所以B→B，这是因为A)
  11.[插话]     句中插废话/数据后加评注
  12.[长短句]   插入短句碎片，改变句长分布
  13.[重复]     关键词局部重复，制造真人写作特征
  14.[堆叠]     同义反复 (至关重要→再怎么强调不为过)
  15.[结论]     结论句泡水 (总之→综上所述)
  16.[ULTRA]    超注水：允许一定语言不通 (ultra only)
  17.[段落]     合并相邻短段落 (ultra only)

v4 改进:
  - 修复 微机电系统（微机电系统（MEMS）） 双重展开 bug
  - 修复 关键词→关键且极为关键词 误匹配
  - 修复 短句碎片重复插入
  - 新增 同义改写引擎 (句式级 paraphrase)
  - 所有变体列表扩容 2-3 倍
  - ultra 连击上限提升至 5 次
"""

import re, os, random, math, statistics, difflib, json
from collections import Counter
from docx import Document

# ═══════════════════════════════════════════════════════════════════════
# 强度配置
# ═══════════════════════════════════════════════════════════════════════

INTENSITY_CONFIG = {
    "light": {
        "deai_prob": 0.0,
        "expand_prob": 0.3,
        "qualifier_prob": 0.25,
        "academic_variant_prob": 0.2,
        "colloquial_prob": 0.15,
        "paraphrase_prob": 0.15,
        "conjunction_prob": 0.2,
        "asymmetric_prob": 0.15,
        "subject_abstract_prob": 0.15,
        "passive_prob": 0.2,
        "reorder_prob": 0.3,
        "filler_prob": 0.2,
        "sentence_mix_prob": 0.15,
        "keyword_repeat_prob": 0.1,
        "redundant_prob": 0.1,
        "conclusion_prob": 0.15,
        "ultra_verbose_prob": 0.0,
        "paragraph_merge_prob": 0.0,
        "cross_reorder_prob": 0.0,
        "emphasis_shift_prob": 0.0,
        "causal_variation_prob": 0.0,
        "multi_transform": 1,
        "llm_pass_prob": 0.0,
    },
    "medium": {
        "deai_prob": 0.3,
        "expand_prob": 0.5,
        "qualifier_prob": 0.5,
        "academic_variant_prob": 0.35,
        "colloquial_prob": 0.3,
        "paraphrase_prob": 0.3,
        "conjunction_prob": 0.4,
        "asymmetric_prob": 0.3,
        "subject_abstract_prob": 0.3,
        "passive_prob": 0.35,
        "reorder_prob": 0.45,
        "filler_prob": 0.45,
        "sentence_mix_prob": 0.3,
        "keyword_repeat_prob": 0.25,
        "redundant_prob": 0.35,
        "conclusion_prob": 0.35,
        "ultra_verbose_prob": 0.0,
        "paragraph_merge_prob": 0.0,
        "cross_reorder_prob": 0.2,
        "emphasis_shift_prob": 0.25,
        "causal_variation_prob": 0.2,
        "multi_transform": 2,
        "llm_pass_prob": 0.0,
    },
    "heavy": {
        "deai_prob": 0.6,
        "expand_prob": 0.75,
        "qualifier_prob": 0.7,
        "academic_variant_prob": 0.55,
        "colloquial_prob": 0.5,
        "paraphrase_prob": 0.5,
        "conjunction_prob": 0.6,
        "asymmetric_prob": 0.5,
        "subject_abstract_prob": 0.5,
        "passive_prob": 0.5,
        "reorder_prob": 0.6,
        "filler_prob": 0.6,
        "sentence_mix_prob": 0.5,
        "keyword_repeat_prob": 0.4,
        "redundant_prob": 0.5,
        "conclusion_prob": 0.5,
        "ultra_verbose_prob": 0.0,
        "paragraph_merge_prob": 0.0,
        "cross_reorder_prob": 0.35,
        "emphasis_shift_prob": 0.4,
        "causal_variation_prob": 0.35,
        "multi_transform": 3,
        "llm_pass_prob": 0.50,
    },
    "ultra": {
        "deai_prob": 0.85,
        "expand_prob": 0.9,
        "qualifier_prob": 0.85,
        "academic_variant_prob": 0.7,
        "colloquial_prob": 0.65,
        "paraphrase_prob": 0.65,
        "conjunction_prob": 0.7,
        "asymmetric_prob": 0.6,
        "subject_abstract_prob": 0.6,
        "passive_prob": 0.6,
        "reorder_prob": 0.7,
        "filler_prob": 0.8,
        "sentence_mix_prob": 0.7,
        "keyword_repeat_prob": 0.6,
        "redundant_prob": 0.7,
        "conclusion_prob": 0.6,
        "ultra_verbose_prob": 0.75,
        "paragraph_merge_prob": 0.3,
        "cross_reorder_prob": 0.5,
        "emphasis_shift_prob": 0.55,
        "causal_variation_prob": 0.5,
        "multi_transform": 3,
        "llm_pass_prob": 0.70,
    },
}

# ═══════════════════════════════════════════════════════════════════════
# 缩写映射（通用 + 领域）
# ═══════════════════════════════════════════════════════════════════════

ABBREVIATIONS = {
    "AI": "人工智能（AI）",
    "ML": "机器学习（ML）",
    "DL": "深度学习（DL）",
    "CNN": "卷积神经网络（CNN）",
    "RNN": "循环神经网络（RNN）",
    "LSTM": "长短期记忆网络（LSTM）",
    "GAN": "生成对抗网络（GAN）",
    "NLP": "自然语言处理（NLP）",
    "CV": "计算机视觉（CV）",
    "IoT": "物联网（IoT）",
    "API": "应用程序编程接口（API）",
    "SVM": "支持向量机（SVM）",
    "PCA": "主成分分析（PCA）",
    "电子鼻": "电子鼻（Electronic Nose, E-Nose）",
    "MEMS": "微机电系统（MEMS）",
    "VOCs": "挥发性有机化合物（VOCs）",
    "ANN": "人工神经网络（ANN）",
    "QCM": "石英晶体微天平（QCM）",
    "MOS": "金属氧化物半导体（MOS）",
    "GC-MS": "气相色谱-质谱联用（GC-MS）",
    "AUC": "曲线下面积（AUC）",
}


# ═══════════════════════════════════════════════════════════════════════
# DE-AI：删除AI高频连接词
# ═══════════════════════════════════════════════════════════════════════

AI_CONNECTIVES = [
    "此外，", "因此，", "同时，", "总之，", "综上所述，",
    "值得注意的是，", "进一步而言，", "除此之外，",
    "需要指出的是，", "从某种意义上来说，", "更进一步地看，",
    "实际上，", "简单来说，", "不难发现，",
    "一言以蔽之，", "总的来说，", "总体而言，",
]

SEQUENCE_MAP = {
    "首先，": "第一，", "首先 ": "第一，",
    "其次，": "另外，", "其次 ": "另外，",
    "最后，": "再者，", "最后 ": "再者，",
}

def de_ai_connectives(text):
    applied = False
    for old, new in SEQUENCE_MAP.items():
        if text.startswith(old):
            text = text.replace(old, new, 1)
            applied = True
            break
    for c in AI_CONNECTIVES:
        if text.startswith(c):
            text = text[len(c):]
            applied = True
            break
    return text, applied


# ═══════════════════════════════════════════════════════════════════════
# 判断句冗余（FIXED_PATTERNS 保护）
# ═══════════════════════════════════════════════════════════════════════

FIXED_PATTERNS = [
    "而是", "但是", "可是", "正是", "而是说", "就是说",
    "而是指", "就是指", "关键词",
]

QUALIFIER_PATTERNS = [
    (r"可以说是([^。，；]*?)的", None),
    (r"是([^。，；]{3,50})(的[^。，；]{0,5}?。)", r"可以说是\1\2"),
    (r"是([^。，；]{3,50})(。)", r"实质上可以说是\1\2"),
    (r"体现了", r"在一定程度上体现出了"),
    (r"揭示了", r"较为深入地揭示了"),
    (r"证明了", r"有力地证明了"),
    (r"印证了", r"进一步印证了"),
    (r"表明", r"清楚地表明"),
    (r"说明", r"充分说明"),
    (r"标志着", r"可以被视为一个标志性的进展，标志着"),
    (r"反映了", r"较为全面地反映出了"),
    (r"展示了", r"充分展示了"),
    (r"指出", r"明确地指出"),
]

def apply_qualifiers(text, prob):
    if random.random() >= prob:
        return text, False
    applied = False
    placeholders = {}
    result = text
    for fp in FIXED_PATTERNS:
        if fp in result:
            ph = f"__FIX_{len(placeholders)}__"
            placeholders[ph] = fp
            result = result.replace(fp, ph)
    for pattern, replacement in QUALIFIER_PATTERNS:
        if replacement is None:
            continue
        if re.search(pattern, result):
            result = re.sub(pattern, replacement, result)
            applied = True
            break
    for ph, fp in placeholders.items():
        result = result.replace(ph, fp)
    return result, applied


# ═══════════════════════════════════════════════════════════════════════
# 口语化学术表达变体（v4 扩容）
# ═══════════════════════════════════════════════════════════════════════

ACADEMIC_VARIANTS = {
    "实验结果表明": [
        "从做出来的实验来看",
        "数据跑完之后发现",
        "结果这一块的意思很明显",
        "看这些实验数据的话",
        "实验这一步给出的反馈是",
        "结果其实已经很明显了",
        "从实验数据来看",
        "结合测试结果可以发现",
        "实验过程中观察到",
        "对结果进行分析后发现",
        "实验数据反映出",
        "梳理实验结果可以看出",
    ],
    "研究表明": [
        "研究下来就是这么个情况",
        "经过这么一折腾发现",
        "琢磨了这么久发现",
        "翻看之前的研究能看出",
        "从研究的实际产出来看",
        "反复推敲过后的结论是",
        "从研究结果来看",
        "分析发现",
        "研究数据显示",
        "深入分析后可知",
        "已有研究结果反映",
        "从现有证据来看",
    ],
    "实验表明": [
        "实验过程中观察到",
        "测试结果反映",
        "实验数据显示",
        "通过实验可以发现",
        "实验给出的大致意思是",
        "实验摸底的结果是",
    ],
    "实验发现": [
        "在实验室里捣鼓出来的结论是",
        "实验这一套流程走完看到",
        "看着实验这一堆东西发现",
        "实验摸底的结果是",
        "这一轮实验干下来发现",
        "实验过程中发现",
        "通过实验观察到",
        "测试结果显示",
    ],
    "结果表明": [
        "从结果来看",
        "根据结果可知",
        "对结果进行梳理可以发现",
        "从所得结果来看",
        "最终结果反映出",
        "从结果中能够看到",
        "结果呈现出",
        "综合结果说明",
    ],
    "结果发现": [
        "最后落到地上的情况是",
        "兜兜转转最后的落脚点在",
        "结果一出来就看明白了",
        "最终的盘点结果指向",
        "顺着结果看过去发现",
        "最后的账算下来是",
        "最终结果反映出",
        "研究过程中观察到",
    ],
    "数据显示": [
        "这些数字本身说明了",
        "盯着这些账面数据看的话",
        "数据层面给出的直观反应是",
        "数字是不会骗人的：",
        "把数据排开来看的话",
        "从数据变化趋势来看",
        "数据结果反映出",
        "统计结果显示",
        "从采集到的信息来看",
        "数值变化说明",
    ],
    "由此可见": [
        "顺着这个由头看过去",
        "这么一来意思就很明朗了",
        "从这些线索中能看出",
        "话说到这个程度也就是说",
        "跟着这个线索看下来",
        "这样看来",
        "由此可以推断",
        "顺着这个逻辑",
        "从这能看出",
        "这么一推",
    ],
    "综上所述": [
        "综合这些结果来看",
        "说了这么多归拢一下",
        "综合这些情况来看",
        "从整体来看",
        "综合以上分析",
        "从整体情况来看",
        "将上述结果汇总后可以发现",
        "综合各方面证据可知",
    ],
    "也就是说": [
        "换一种表述方式",
        "翻译过来就是",
        "用通俗的话来说",
        "也就是说这么个理",
        "讲得直白一点就是",
        "归根结底意思就是",
        "换个说法",
        "说得直接一点",
        "可以理解为",
        "从本质上讲",
        "归结起来就是",
    ],
}

def apply_academic_variants(text, prob):
    if random.random() >= prob:
        return text, False
    applied = False
    result = text
    for old, variants in ACADEMIC_VARIANTS.items():
        if old in result:
            new = random.choice(variants)
            result = result.replace(old, new, 1)
            applied = True
            break
    return result, applied


# ═══════════════════════════════════════════════════════════════════════
# 同义改写引擎 — 句式级 paraphrase（v4 新增）
# ═══════════════════════════════════════════════════════════════════════

PARAPHRASE_PATTERNS = [
    # A导致B → B与A密切相关
    (r"([^。，；]{6,30})(导致|使得|致使)([^。，；]{6,40})",
     r"\3与\1有着密不可分的内在联系"),
    # A对B有影响 → B受到A的影响
    (r"([^。，；]{4,20})对([^。，；]{4,30})有(显著的|明显的|重要的|一定的)(影响|作用)",
     r"\2在相当程度上受到\1的\3\4"),
    # A是B的关键 → B的关键在于A
    (r"([^。，；]{4,30})是([^。，；]{4,30})的(关键|核心|基础|前提)",
     r"\2的\3在很大程度上取决于\1"),
    # A取决于B → A与B密切相关
    (r"([^。，；]{4,30})(取决于|依赖于|决定于)([^。，；]{4,30})",
     r"\1与\3之间存在密切的关联关系"),
    # A分为B和C → A可以归纳为B与C两大类
    (r"([^。，；]{4,30})分为([^。，；]{4,30})和([^。，；]{4,30})",
     r"\1可以进一步归纳为\2与\3两个主要类别"),
    # A包括B → A主要涵盖B等方面
    (r"([^。，；]{4,30})包括([^。，；]{8,60})",
     r"\1主要包括以下几个方面的内容：\2"),
    # A具有B特性 → A呈现出鲜明的B特性
    (r"([^。，；]{6,30})具有([^。，；]{4,30})的(特点|特征|特性|属性)",
     r"\1呈现出十分鲜明的\2的\3"),
    # A需要B → A对B有着迫切的需求（回避过去时"需要了"、"需要推动了"等）
    (r"([^。，；]{4,30})需要(?![^。，；]*[了过])([^。，；]{4,50})",
     r"\1对\2有着较为迫切的需求"),
    # 通过A，实现B → 借助A这一途径，B得以实现
    (r"通过([^。，；]{4,30})，([^。，；]{6,50})(实现|达到|完成)",
     r"借助\1这一途径，\2得以较为顺利地\3"),
]

def apply_paraphrase(text, prob):
    if random.random() >= prob:
        return text, False
    for pat, rep in PARAPHRASE_PATTERNS:
        if re.search(pat, text):
            return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 句首插废话 — 统一前缀池（v5 合并口语+句首列表）
# ═══════════════════════════════════════════════════════════════════════

# 禁用前缀：表达主观判断/立场/评价，不适合引导学术论文中的事实陈述句
DISABLED_PREFIXES = {
    "基本上可以断定，", "凭经验来讲，", "凭经验看，", "老实讲，",
    "说句公道话，", "说句实在话，", "坦白讲，", "平心而论，",
    "客观地讲，", "说得不好听一点，", "要我说，", "说一千道一万，",
    "说来说去，", "说真的，", "多少带点主观色彩地说，",
    "说穿了，", "说到底，", "实话实说，", "认真说来，",
}

# 总结性前缀：仅适合段落末句
SUMMARY_PREFIXES = {
    "说来说去，", "说到底还是那句话：", "归结起来就是，",
    "归根结底一句话，",
}

SENTENCE_PREFIXES = [
    # 原 SHORT_CONJUNCTIONS
    "说白了，", "其实，", "这个问题的关键在于：",
    "从实际来看，", "话说回来，", "说到这里，",
    "顺带一提，", "直白点讲，",
    "实话实说，", "回过头来看，", "这么看的话，",
    "仔细想想看，", "单看这一点的话，",
    "把这层意思拆开来看，", "有个值得注意的现象：",
    "把视线拉回来，", "退一步讲，",
    "归根结底一句话，", "稍微留意一下就会发现，",
    "摊开了说，", "要说最直观的，",
    "有个事实很清楚：", "从底层逻辑来看，",
    "接着说，", "从一个侧面看，",
    "反过来说，", "严格来讲，", "再引申一下，",
    "不止如此，", "更关键的是，", "问题在于，",
    "说句公道话，", "凭经验看，",
    "说起来，", "整体上看，",
    "细究起来，", "说一千道一万，", "绕回来，",
    "更有意思的是，", "要我说，", "顺着这个逻辑，",
    "说穿了，", "仔细琢磨，", "退一步说，",
    "老实讲，", "认真说来，", "补充一点，",
    "把范围缩小一点看，", "说得不好听一点，",
    "从逻辑链条上看，", "掐头去尾来看，",
    "换个问法，", "打个比方，",
    "从逻辑上推，", "有趣的一点是，",
    "往往被忽略的是，", "再往深想一层，",
    "就事论事地讲，", "先抛开结论，",
    "凭经验来讲，", "印象很深的是，",
    # 原 LONG_CONJUNCTIONS（去重）
    "顺着这个思路往下看，",
    "如果把视线拉远一些，",
    "如果聚焦到这一环节，",
    "从现象本身出发，",
    "就目前掌握的信息而言，",
    "就实验过程而言，",
    "回顾整个过程，",
    "沿着这一逻辑继续分析，",
    "进一步分析的话，",
    "再看另一组数据，",
    "再结合相关结果来看，",
    "联系实际应用场景，",
    "放在具体背景下看，",
    "从更深层的角度来看，",
    "把视线拉远至整个领域，",
    "从这一角度切入分析，",
    "把前因后果串起来看，",
    "说到底还是那句话：",
    # 原 COLLOQUIAL_OPENERS（去重）
    "也就是说，", "换句话说，", "不难看出，",
    "我们不妨这样理解：", "本质上来说，",
    "换一个角度来看，", "简单理解的话，", "直观来看，",
    "平心而论，", "客观地讲，", "某种程度上，",
    "难理解的是，", "说句实在话，", "细想之下，", "不得不说的是，",
    "坦白讲，", "如果再往深处想，",
    "话虽如此，", "很大程度上来讲，",
    "按照通常的理解，", "基本上可以断定，",
    "从经验上来说，", "拐个弯来说，",
    "多少带点主观色彩地说，", "站在研究的角度，",
    "从另一个侧面来看",
]

# 去重保持顺序
SENTENCE_PREFIXES_UNIQUE = []
_seen = set()
for p in SENTENCE_PREFIXES:
    if p not in _seen and p not in DISABLED_PREFIXES:
        _seen.add(p)
        SENTENCE_PREFIXES_UNIQUE.append(p)

# 去掉尾标点的集合，用于 guard 检查
SENTENCE_PREFIXES_SET = {p.rstrip("，：") for p in SENTENCE_PREFIXES_UNIQUE}


# ═══════════════════════════════════════════════════════════════════════
# 不对称结构
# ═══════════════════════════════════════════════════════════════════════

ASYMMETRIC_PATTERNS = [
    (r"不仅([^。，；]{4,30})，而且([^。，；]{4,40})",
     r"不仅\1，而且在某些条件下\2也能实现"),
    (r"既([^。，；]{4,30})又([^。，；]{4,30})",
     r"既具有\1的特征，同时\2的属性也表现得较为明显"),
    (r"提高了([^。，；]{4,30})和([^。，；]{4,30})",
     r"提高了\1，\2也得到了相应改善"),
    (r"([^。，；]{4,30})与([^。，；]{4,30})的(对比|差异|区别)",
     r"\1和\2之间的\3是两个值得关注的不同维度"),
    (r"([^。，；]{4,30})和([^。，；]{4,30})两方面",
     r"\1方面固然重要，\2方面的作用同样不容忽视"),
    (r"从([^。，；]{4,30})和([^。，；]{4,30})(.*?)(来看|出发)",
     r"既要从\1的角度加以考察，也需要从\2的维度\4"),
    (r"随着([^。，；]{4,30})的(发展|提高|增长|增加)",
     r"在\1不断\2的大背景之下"),
]

def apply_asymmetric(text, prob):
    if random.random() >= prob:
        return text, False
    for pat, rep in ASYMMETRIC_PATTERNS:
        if re.search(pat, text):
            return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 主语抽象化
# ═══════════════════════════════════════════════════════════════════════

ABSTRACT_SUBJECTS = [
    (r"^这(?!一|种|些)", ["这一现象", "上述情况"]),
]

def apply_abstract_subject(text, prob):
    if random.random() >= prob:
        return text, False
    for pattern, replacements in ABSTRACT_SUBJECTS:
        if re.match(pattern, text):
            subj = random.choice(replacements)
            return re.sub(f"^{pattern}", subj, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 被动化短语替换
# ═══════════════════════════════════════════════════════════════════════

PASSIVE_REPLACEMENTS = [
    ("推动了", "起到了推动作用，使"),
    ("促进了", "起到了促进作用"),
    ("提升了", "使……得到了提升"),
    ("催生了", "起到了催生作用，促成了"),
    ("增强了", "使……得到了增强"),
    ("改善了", "使……状况得到了改善"),
    ("加大了", "使……力度得到了加大"),
    ("深化了", "使……得到了进一步深化"),
]

def apply_passive(text, prob):
    if random.random() >= prob:
        return text, False
    for old, new in PASSIVE_REPLACEMENTS:
        if old in text:
            return text.replace(old, new, 1), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 语序颠倒
# ═══════════════════════════════════════════════════════════════════════

REORDER_PATTERNS = [
    (r"因为([^。，；]{4,40})，所以([^。，；]{4,60})", r"\2，这主要是因为\1"),
    (r"由于([^。，；]{4,40})，([^。，；]{4,60})", r"\2，这主要是由于\1"),
    (r"虽然([^。，；]{4,40})，但([^。，；]{4,60})", r"\2，尽管\1"),
    (r"([^。，；]{8,30})具有([^。，；]{4,30})的(特点|特征|属性)", r"从\1来看，其显著的\3在于\2"),
    (r"([^。，；]{8,40})在于([^。，；]{4,40})", r"\1可以被进一步归纳为\2"),
    (r"只要([^。，；]{4,30})就([^。，；]{4,40})", r"\2的前提条件是\1"),
]

def apply_reorder(text, prob):
    if random.random() >= prob:
        return text, False
    for pat, rep in REORDER_PATTERNS:
        if re.search(pat, text):
            return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 句中插废话 / 数据后加评注（v4 扩容变体）
# ═══════════════════════════════════════════════════════════════════════

MID_SENTENCE_FILLERS = [
    ("——", "——这里需要特别强调的是，"),
    ("——", "——从实际效果来看，"),
    ("——", "——进一步分析可以发现，"),
    ("——", "——结合实际情况来看，"),
    ("——", "——这一点在后续分析中还会涉及，"),
    ("——", "——这其中的逻辑并不复杂，"),
    ("——", "——从长远来看，"),
    ("——", "——从更广泛的意义上说，"),
    ("——", "——换一个角度来看这个问题，"),
    ("——", "——如果仔细推敲的话，"),
    ("——", "——用更专业的表述来说，"),
    ("——", "——从理论层面来看，"),
    ("——", "——落实到具体实践中，"),
    ("——", "——深入一层来看这个问题，"),
    ("——", "——这其实并不难理解，"),
]

POST_CLAIM_FILLERS = [
    # 匹配单个百分比值，排除 "71%-100%" 这类范围
    (r'(?<!\d%[–\-至])\b(\d+(?:\.\d+)?%)(?!\s*[–\-至]\s*\d)', r'\1，这一数据颇具说服力'),
    (r'(?<!\d%[–\-至])\b(\d+(?:\.\d+)?%)(?!\s*[–\-至]\s*\d)', r'\1，这并非一个可以忽视的数字'),
    (r'(?<!\d%[–\-至])\b(\d+(?:\.\d+)?%)(?!\s*[–\-至]\s*\d)', r'\1，这是一个值得关注的数值'),
    (r'(?<!\d%[–\-至])\b(\d+(?:\.\d+)?%)(?!\s*[–\-至]\s*\d)', r'\1，这一比例充分说明了问题的实质'),
    (r'(?<!\d%[–\-至])\b(\d+(?:\.\d+)?%)(?!\s*[–\-至]\s*\d)', r'\1，这组数据具有较强的参考价值'),
]

# Track which fillers we've used globally to reduce repetition
_used_fillers = set()
_used_fragments = set()

def apply_fillers(text, prob):
    global _used_fillers
    if random.random() >= prob:
        return text, False
    for old, new in MID_SENTENCE_FILLERS:
        if old in text:
            if new not in _used_fillers or random.random() < 0.3:
                _used_fillers.add(new)
                return text.replace(old, new, 1), True
            else:
                # try another variant
                continue
    for pat, rep in POST_CLAIM_FILLERS:
        if re.search(pat, text):
            if rep not in _used_fillers or random.random() < 0.3:
                _used_fillers.add(rep)
                return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 口语化元素 — 在句式中插入口语/人话表达（降低AI痕迹）
# ═══════════════════════════════════════════════════════════════════════

# 句内插入元素（保留，与 SENTENCE_PREFIXES_UNIQUE 不冲突）
COLLOQUIAL_PARENTHETICAL = [
    ("说白了", "，"),
    ("也就是说", "，"),
    ("换句话说", "，"),
    ("其实", "，"),
    ("不妨说", "，"),
    ("进一步讲", "，"),
    ("平心而论", "，"),
    ("客观地看", "，"),
    ("说到底", "，"),
    ("严格来说", "，"),
    ("再引申一步", "，"),
    ("从另一个角度说", "，"),
]

def apply_colloquial(text, prob):
    """在句中插入口语化元素。分两种模式：
    1. 句首替换：如果句首是正式连接词，替换为 SENTENCE_PREFIXES_UNIQUE 中口语风格的表达
    2. 句中插入：在句子中间插入"说白了"等语气停顿
    """
    if random.random() >= prob:
        return text, False
    mode = random.choice(["opener", "parenthetical"])

    if mode == "opener":
        # 句首替换：对第一句或第二句下手
        sentences = re.split(r'(?<=[。！？])', text)
        if len(sentences) < 2:
            return text, False
        idx = random.randint(0, min(1, len(sentences) - 1))
        s = sentences[idx].strip()
        # 声明性/引用性内容 → 不适合被评价前缀引导
        if _is_declarative_opener(s) or _is_table_or_figure_ref(s):
            return text, False
        # 互斥守卫：如果该句已以 SENTENCE_PREFIXES_SET 开头，跳过
        already_has_prefix = any(s.startswith(p) for p in SENTENCE_PREFIXES_SET)
        if already_has_prefix:
            return text, False
        # 检查是否以正式学术套话开头
        formal_starters = [
            "值得注意的是", "进一步而言", "除此之外", "需要指出的是",
            "从某种意义上来说", "事实上", "实际上", "可以说",
        ]
        for fs in formal_starters:
            if s.startswith(fs):
                # 替换为口语表达
                colloquial = random.choice(SENTENCE_PREFIXES_UNIQUE)
                rest = s[len(fs):] if len(s) > len(fs) else s
                sentences[idx] = colloquial + rest
                return "".join(sentences), True
        # 没有正式开头，直接插口语开头
        colloquial = random.choice(SENTENCE_PREFIXES_UNIQUE)
        # 如果原句以连接词开头，去掉连接词避免"话虽如此，然而"
        s_stripped = s.lstrip()
        conj_match = re.match(r'^(然而|不过|但是|但|可是|所以|因此|故而|于是|而且|并且)', s_stripped)
        if conj_match:
            rest = s_stripped[conj_match.end():]
            sentences[idx] = colloquial + rest
        else:
            sentences[idx] = colloquial + s
        return "".join(sentences), True

    else:
        # 句中插入：在句子中间插入"说白了"等
        sentences = re.split(r'(?<=[。！？])', text)
        viable = []
        for i, s in enumerate(sentences):
            clean = s.strip()
            if 15 < len(clean) < 100 and "说白了" not in clean and "也就是说" not in clean:
                viable.append(i)
        if not viable:
            return text, False
        idx = random.choice(viable)
        s = sentences[idx].strip()
        # 在句中第一个逗号后插入口语片段
        m = re.search(r'，', s)
        if m and m.start() > 3:
            pos = m.start()
            phrase = random.choice(COLLOQUIAL_PARENTHETICAL)
            sentences[idx] = s[:pos+1] + phrase[0] + phrase[1] + s[pos+1:]
            return "".join(sentences), True
        return text, False


def apply_conjunctions(text, prob):
    """在句首插入连接词/口语前缀。共用 SENTENCE_PREFIXES_UNIQUE 池。"""
    if random.random() >= prob:
        return text, False
    sentences = re.split(r'(?<=[。！？])', text)
    if len(sentences) < 2:
        return text, False
    # 只选非首句，且长度适中
    candidates = []
    for i, s in enumerate(sentences):
        clean = s.strip()
        if i == 0:
            continue
        if len(clean) < 8:
            continue
        # 互斥守卫：如果该句已经以 SENTENCE_PREFIXES_SET 开头，跳过
        already_has_prefix = any(clean.startswith(p) for p in SENTENCE_PREFIXES_SET)
        if already_has_prefix:
            continue
        # 表/图引用、章节号、声明性自指 → 不适合被前缀引导
        if _is_table_or_figure_ref(clean):
            continue
        # 编号列表项 → 不适合被前缀引导
        if _is_list_item(clean):
            continue
        candidates.append(i)
    if not candidates:
        return text, False
    idx = random.choice(candidates)
    # 非末句不选总结性前缀
    is_last = idx >= len(sentences) - 2
    if is_last:
        prefix = random.choice(SENTENCE_PREFIXES_UNIQUE)
    else:
        safe = [p for p in SENTENCE_PREFIXES_UNIQUE if p not in SUMMARY_PREFIXES]
        if not safe:
            safe = SENTENCE_PREFIXES_UNIQUE
        prefix = random.choice(safe)
    sentences[idx] = prefix + sentences[idx].lstrip()
    return "".join(sentences), True


# ═══════════════════════════════════════════════════════════════════════
# 长短句混合 — 插入短碎片改变句长分布（v4 扩容 + 去重）
# ═══════════════════════════════════════════════════════════════════════

SHORT_FRAGMENTS = [
    "这一点很能说明问题。",
    "背后的道理并不复杂。",
    "这是实践中反复验证过的。",
    "这样的情况并不少见。",
    "谁也绕不过去这一关。",
    "这个问题就有点意思了。",
    "这本身就是一个需要认真对待的问题。",
    "里面的门道其实不少。",
    "这个问题值得认真对待。",
    "逻辑上完全可以说得通。",
    "核心就在这儿了。",
    "这在逻辑上是完全站得住脚的。",
    "这一点几乎成了公认的道理。",
    "道理大家都懂，关键就在这。",
    "这也是最值得关注的地方。",
    "这样的例子还可以举出很多。",
    "这一判断在实践中得到了反复验证。",
    "这是值得进一步关注的问题。",
    "这一结论与前述分析在逻辑上保持一致。",
    "这构成了后文讨论的基础。",
]

def apply_sentence_mix(text, prob):
    global _used_fragments
    if random.random() >= prob:
        return text, False
    sentences = re.split(r'(?<=[。！？])', text)
    if len(sentences) <= 4:
        return text, False
    idx = random.randint(2, len(sentences) - 3)
    for check_idx in [idx - 1, idx, idx + 1]:
        if check_idx < len(sentences):
            for frag in SHORT_FRAGMENTS:
                if frag in sentences[check_idx]:
                    return text, False
    available = [f for f in SHORT_FRAGMENTS if f not in _used_fragments]
    if not available:
        available = SHORT_FRAGMENTS
    fragment = random.choice(available)
    _used_fragments.add(fragment)
    sentences.insert(idx + 1, fragment)
    return "".join(sentences), True


# ═══════════════════════════════════════════════════════════════════════
# 关键词局部重复
# ═══════════════════════════════════════════════════════════════════════

def extract_keyword(sentence):
    """提取句中合适的主题词（3-4字），优先句首主题词。"""
    # 优先取引号内的内容
    m = re.search(r'[「"]([^」"]{2,3})[」"]', sentence)
    if m:
        return m.group(1)
    bad_prefixes = {'在', '从', '对', '把', '为', '与', '以', '向', '用', '由', '被', '将', '于', '据', '按', '照', '随'}
    bad_keywords = {'本文', '这个', '一种', '可以', '通过', '同时', '然而', '因此', '此外', '但是', '目前', '首先', '其次', '然后', '之后', '以前', '主要', '进行', '相关', '不同', '较为', '采用', '总体而言', '综上', '综上所述', '不可否认', '关键词', '摘要'}
    # POS 过滤：的+3-4字 后紧跟 下/上/中/后/前 → 丢弃
    pos_bad_tails = {'下', '上', '中', '后', '前'}

    # 优先取句首主题词：句首第一个连续3-4字的词（跳过虚词后）
    head = sentence.strip()[:20]
    # 匹配句首「关键词」模式：开头就是3-4字名词性短语
    m = re.match(r'^([一-鿿]{3,4})(?:[，。；：]|$)', head)
    if m:
        kw = m.group(1)
        if kw[0] not in bad_prefixes and kw[:2] not in bad_keywords and kw not in bad_keywords:
            return kw
    # 匹配「的」后面的关键词：的+3-4字+标点/空格，加 POS 过滤
    m = re.search(r'(?<=的)([一-鿿]{3,4})(?=[，。；：\s)）\]】])', sentence[:40])
    if m:
        kw = m.group(1)
        if kw[0] not in bad_prefixes and kw[:2] not in bad_keywords and kw not in bad_keywords:
            # POS 过滤：关键词末字为 下/上/中/后/前（动词粒子化）→ 丢弃
            if kw[-1] in pos_bad_tails:
                return None
            return kw
    # 句尾关键词：在段落前50字内找 ，…的+名词+。！？
    head50 = sentence.strip()[:50]
    m = re.search(r'，[^。！？]{0,30}的([一-鿿]{3,4})[。！？]', head50)
    if m:
        kw = m.group(1)
        if kw[0] not in bad_prefixes and kw[:2] not in bad_keywords and kw not in bad_keywords:
            return kw
    return None

def apply_keyword_repeat(text, prob):
    if random.random() >= prob:
        return text, False
    sentences = re.split(r'(?<=[。！？])', text)
    if len(sentences) < 3:
        return text, False
    idx = random.randint(0, len(sentences) - 3)
    kw = extract_keyword(sentences[idx])
    if not kw or len(kw) < 3:
        return text, False
    next_s = sentences[idx + 1].strip()
    if len(next_s) < 12:
        return text, False
    # 检查关键词是否已经在下一句开头出现（避免重复）
    if kw in next_s[:len(kw) + 2]:
        return text, False
    # 检查关键词末尾和下一句开头是否有字符重叠（避免 "马克思主义实细想之下"）
    overlap = 0
    for j in range(min(2, len(kw)), 0, -1):
        if kw[-j:] == next_s[:j]:
            overlap = j
            break
    if overlap > 0:
        kw = kw[:-overlap]
    if not kw or len(kw) < 2:
        return text, False
    sentences[idx + 1] = kw + next_s
    return "".join(sentences), True


# ═══════════════════════════════════════════════════════════════════════
# 同义反复（v4 扩容）
# ═══════════════════════════════════════════════════════════════════════

REDUNDANT_PATTERNS = [
    (r"至关重要", "至关重要，这一点无论怎么强调都不为过"),
    (r"不可忽视", "不可忽视，需要引起足够重视"),
    (r"具有重要的意义", "具有重要意义，值得我们进一步深入思考"),
    (r"充分体现", "充分体现，这是一个非常明显的特征"),
    (r"不可避免地", "不可避免地，这是客观规律的体现"),
    (r"显著的", "显著的，也可以说是非常突出的"),
    (r"严重的", "严重的，情况不容乐观"),
    (r"必然趋势", "必然趋势，这一点在实践中已经得到反复验证"),
    (r"非常(重要|关键|必要)", "极其\1，甚至可以说是不容置疑的"),
    (r"复杂的", "复杂的，涉及多个层面的交互影响"),
    (r"普遍的", "普遍的，在多个领域都有类似表现"),
    (r"本质上(是|属于|体现)", r"本质上或者说从根本上来说\1"),
    (r"可以(看作|视为|理解为|归为)", r"在相当程度上可以被\1为"),
    (r"(?<!从侧面)反映(?!出了)", r"从侧面反映出了"),
    (r"(?<!分地)体现(?![了出])", r"较为充分地体现出了"),
    (r"(?<!推动并促)推动(?!并促进)", r"在很大程度上推动并促进了"),
    (r"不可(避免|缺少|分割)", r"在逻辑上不可\1，这一点具有必然性"),
    (r"决定性", r"具有决定性意义，可以说是起关键作用的"),
    (r"关键(因素|环节|作用|问题)", r"\1，可以说是整个链条中最核心的一环"),
    (r"深入(分析|研究|探讨)", r"更为系统和深入的\1"),
]

def apply_redundant(text, prob):
    if random.random() >= prob:
        return text, False
    for pat, rep in REDUNDANT_PATTERNS:
        if re.search(pat, text):
            return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 结论句泡水（v4 扩容）
# ═══════════════════════════════════════════════════════════════════════

CONCLUSION_FILLERS = [
    (r"^(总而言之|总之|综上|总体而言)(.{10,60})", r"说了这么多，核心意思很明确：\2"),
    (r"^(总而言之|总之|综上|总体而言)(.{10,60})", r"回顾整个分析过程，有一点很清楚：\2"),
    (r"^(总而言之|总之|综上|总体而言)(.{10,60})", r"盘完所有情况，结论很直接：\2"),
    (r"^(可以说)(.{10,60})", r"毫不夸张地说，\2"),
    (r"^(简而言之|简言之)(.{10,60})", r"用一句话来概括，\2"),
    (r"^(可见|由此可见)(.{10,60})", r"由此可以清楚地看到，\2"),
    (r"^(综上所述)(.{10,60})", r"综合以上分析，\2，这一点是比较明确的"),
    (r"^(综上所述)(.{10,60})", r"将上述结果汇总后可以发现，\2"),
]

def apply_conclusion(text, prob):
    if random.random() >= prob:
        return text, False
    for pat, rep in CONCLUSION_FILLERS:
        if re.search(pat, text):
            return re.sub(pat, rep, text), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# ULTRA ONLY — 超注水：允许一定语言不通
# ═══════════════════════════════════════════════════════════════════════

ULTRA_VERBOSE_PATTERNS = [
    # 1. 进行插入
    (r"进行(分析|研究|检测|测试|计算|验证|比较)",
     r"对相关方面展开\1工作，进行深入\1"),
    # 2. 同义堆叠（加词边界）
    (r"\b(重要|关键|核心|显著|突出)(?!词)\b", r"\1且极为\1"),
    # 3. 冗余方向/角度（只替换一次）
    (r"(方面|领域|角度)", lambda m: "诸多的" + m.group(1) + "和多个相关维度"),
    # 4. 句首连接词删除（只删句首）
    (r"^(因此|所以|但是|然而|不过)", ""),
    # 5. 从X来看 → 如果从实际的X情况来看的话
    (r"^(从)([^。，；]{8,30})来看", r"如果从实际的\2情况来看的话"),
    # 6. 大量的大量的
    (r"大量([^。，；]{2,8})", r"大量的大量的\1"),
    # 7. 系列化
    (r"(问题|因素|原因|挑战)", r"一系列\1和相关因素"),
    # 8. 对于→对于...而言
    (r"对于([^。，；]{4,20})，", r"对于\1而言，针对其具体情况，"),
    # 9. 所谓（仅在句首，防止匹配 "这个"的中间）
    (r"^所谓", r"我们通常所说的这种所谓的"),
]

def apply_ultra_verbose(text, prob):
    if random.random() >= prob:
        return text, False
    applied = False
    result = text
    n_hits = random.randint(1, 4)
    for i, pattern in enumerate(ULTRA_VERBOSE_PATTERNS):
        if i >= n_hits * 2:  # 最多试 n_hits*2 个pattern
            break
        if isinstance(pattern[1], str):
            pat, rep = pattern
            if re.search(pat, result):
                result = re.sub(pat, rep, result, count=1)
                applied = True
        else:
            # lambda callable
            pat, func = pattern
            if re.search(pat, result):
                result = re.sub(pat, func, result, count=1)
                applied = True
    return result, applied


# ═══════════════════════════════════════════════════════════════════════
# 跨句信息重排 — 将上句尾从句移到下句首（反降重手法）
# ═══════════════════════════════════════════════════════════════════════

def apply_cross_reorder(text, prob):
    """跨句重排：把A句尾从句移到B句首，或B句首连接词移到A句尾。"""
    if random.random() >= prob:
        return text, False
    sentences = re.split(r'(?<=[。！？])', text)
    if len(sentences) < 2:
        return text, False
    # 只对非末句+下一句操作
    candidates = []
    for i in range(len(sentences) - 1):
        a = sentences[i].strip()
        b = sentences[i + 1].strip()
        if len(a) >= 10 and len(b) >= 10 and len(a) <= 120 and len(b) <= 120:
            candidates.append(i)
    if not candidates:
        return text, False
    idx = random.choice(candidates)
    a = sentences[idx].strip()
    b = sentences[idx + 1].strip()

    # 模式1: A句尾是"，"引导的从句 → 移到B句首
    m = re.search(r'[，]([^，。！？]{6,25})$', a)
    if m and random.random() < 0.5:
        clause = m.group(1)
        sentences[idx] = a[:m.start()] + '。'
        sentences[idx + 1] = clause + '，并且' + b
        return "".join(sentences), True

    # 模式2: B句首有连接词 → 移到A句尾
    conj_match = re.match(r'^(此外|因此|然而|但是|所以|同时|于是|而且)', b)
    if conj_match:
        conj = conj_match.group(1)
        rest = b[conj_match.end():].lstrip('，,')
        sentences[idx] = a.rstrip('。') + '，' + conj + '。'
        sentences[idx + 1] = rest
        return "".join(sentences), True

    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 轻重程度转换 — 强弱程度词互换（反降重手法）
# ═══════════════════════════════════════════════════════════════════════

EMPHASIS_WEAKEN = [
    ('显著', '较为明显'),
    ('非常', '比较'),
    ('特别', '相当'),
    ('极其', '相当'),
    ('核心', '较为主要'),
    ('关键', '较为重要'),
    ('完全', '基本'),
    ('充分', '较为充分'),
    ('必然', '在很大程度上'),
]

EMPHASIS_STRENGTHEN = [
    ('较好', '显著'),
    ('一定', '充足的'),
    ('一些', '多方面的'),
    ('有助于', '有效促进'),
    ('可能', '在一定程度上'),
    ('比较', '较为'),
]

def apply_emphasis_shift(text, prob):
    """随机选择强化或弱化方向，替换1-2个程度词。"""
    if random.random() >= prob:
        return text, False
    if len(text) < 15:
        return text, False
    # 选方向
    table = random.choice([EMPHASIS_WEAKEN, EMPHASIS_STRENGTHEN])
    applied = False
    result = text
    count = 0
    for old, new in table:
        if count >= random.randint(1, 2):
            break
        if old in result and new not in result:
            result = result.replace(old, new, 1)
            applied = True
            count += 1
    return result, applied


# ═══════════════════════════════════════════════════════════════════════
# 因果句式变换 — 改变因果结构表达（反降重手法）
# ═══════════════════════════════════════════════════════════════════════

CAUSAL_PATTERNS = [
    (r'由于([^，。]{6,30})，因此([^。]{8,40}。)',
     r'之所以\2，这在很大程度上是因为\1'),
    (r'通过([^，。]{6,25})，([^。]{8,35}了)',
     r'以\1为基础和出发点，\2'),
    (r'([一-鿿]{2,10})促进了([^，。]{6,30}。)',
     r'以\1为推动因素，\2的相关发展得到了推动'),
]

def apply_causal_variation(text, prob):
    """替换因果句式结构，增加句式多样性。"""
    if random.random() >= prob:
        return text, False
    if len(text) < 25:
        return text, False
    for pat, rep in CAUSAL_PATTERNS:
        if re.search(pat, text):
            return re.sub(pat, rep, text, count=1), True
    return text, False


# ═══════════════════════════════════════════════════════════════════════
# 段落合并（ultra only）
# ═══════════════════════════════════════════════════════════════════════

def apply_paragraph_merge(paragraphs, prob):
    if random.random() >= prob:
        return paragraphs
    if len(paragraphs) < 2:
        return paragraphs
    for i in range(len(paragraphs) - 1):
        p1 = paragraphs[i].strip()
        p2 = paragraphs[i + 1].strip()
        if not p1 or not p2:
            continue
        if len(p1) < 60 and len(p2) < 60 and p1.endswith("。"):
            connectors = ["此外，", "同时，", "另外，", "进一步而言，", "除此之外，", "从另一方面来说，"]
            conn = random.choice(connectors)
            paragraphs[i] = p1 + conn + p2
            paragraphs[i + 1] = ""
            break
    return paragraphs


# ═══════════════════════════════════════════════════════════════════════
# 段落过滤器
# ═══════════════════════════════════════════════════════════════════════

def is_heading_text(text):
    return len(text) < 30 and not text.endswith("。") and not re.search(r"\[\d+\]", text)

def is_reference_line(text):
    return bool(re.match(r"^\[\d+\]", text))

def is_short_label(text):
    return len(text) < 20 and ("：" in text or "   " in text or "关键词" in text)


# ── 句类判断守卫 ──

def _is_table_or_figure_ref(sentence):
    """后句是否以表/图引用、章节号或声明性自指开头（不适合被前缀引导）。"""
    s = sentence.strip()
    return bool(re.match(r'^(表|图|第[一二三四五六七八九十\d]+[章节])', s)) or \
           bool(re.match(r'^(本文|该中心|该机构)', s))

def _is_declarative_opener(sentence):
    """句子是否以声明性/事实性语言开头（不适合被评价前缀引导）。"""
    s = sentence.strip()
    markers = [
        '本文', '该', '此', '第', '上海', 'NASA', 'DLR', '欧洲', '俄罗斯',
        '中国', '美国', '全球', '在', '按照', '通过', '基于', '从',
        '中', '英', '民航', 'AFRC', 'ONERA', 'ARJ', 'C9',
        '这一', '这种', '上述',
    ]
    return any(s.startswith(m) for m in markers)

def _is_list_item(sentence):
    """是否为编号列表项（1. 2. (1) 等开头）。"""
    return bool(re.match(r'^[\s]*[(（]?\d+[)）.．、\s]', sentence.strip()))


# ═══════════════════════════════════════════════════════════════════════
# 缩写展开（v4 修复：双重展开）
# ═══════════════════════════════════════════════════════════════════════

def apply_expand(text, prob):
    if random.random() >= prob:
        return text, False
    applied = False
    result = text
    for abbr, expanded in ABBREVIATIONS.items():
        if abbr not in result:
            continue
        # 纯英文缩写加字母边界检查（防止 DLR→深度学习（DL）R）
        if abbr.isascii() and len(abbr) >= 2:
            pattern_boundary = r'(?<![a-zA-Z])' + re.escape(abbr) + r'(?![a-zA-Z])'
            if not re.search(pattern_boundary, result):
                continue
        # 检查是否已展开过：缩写后紧跟「(」或「（」
        # 例如 "电子鼻（Electronic Nose, E-Nose）" 中的 "电子鼻（"
        if re.search(re.escape(abbr) + r'[（(]', result):
            continue
        # 检查缩写是否出现在括号内（如 "微机电系统（MEMS）" 中的 MEMS）
        if re.search(r'[（(][^）)]*' + re.escape(abbr) + r'[^）)]*[）)]', result):
            continue
        if f"也就是{abbr}" in result or f"即{abbr}" in result:
            continue
        result = result.replace(abbr, expanded, 1)
        applied = True
        break
    return result, applied


# ═══════════════════════════════════════════════════════════════════════
# 结构性反向检查
# ═══════════════════════════════════════════════════════════════════════

def is_well_formed(text):
    """快速结构性检查：括号配对、末尾标点、连续标点、空括号。"""
    if len(text.strip()) < 4:
        return False
    # 括号配对
    for left, right in [('（', '）'), ('(', ')'), ('【', '】'), ('"', '"'), ('"', '"')]:
        if text.count(left) != text.count(right):
            return False
    # 末尾标点：不以 ，；：、 结束
    if text.rstrip()[-1] in '，；：、':
        return False
    # 连续标点
    if re.search(r'[。！？，；：、]{2,}', text):
        return False
    # 空括号
    if re.search(r'[（(]\s*[）)]', text):
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════
# LLM 层注水 — 训练集约束模板
# ═══════════════════════════════════════════════════════════════════════

# 句长角色轮转 (A/B/C): 用于 L1 段内改写的子 agent 分配
SENTENCE_ROLE_HINTS = [
    "特别注意：把其中一句缩短到10-20字。",
    "特别注意：把其中一句拉长到40-60字。",
    "特别注意：长短句差距拉大，混用。",
]

# L1: 段内改写 Prompt — 用于 C5.5C/T6.7C Stage L1 子 agent
LLM_INTRA_PROMPT = """你是一个文本改写助手。改写下面这段学术文字，让它读起来更像真人写的。

> 注意：输入文本已经过自动替换。先看一下哪些词已经改过了，只处理残留的部分，不要重复。

## 要改什么

【检查残留的AI高频词】
- 检查原文还有没有「通过」「将」「其」「因此」「导致」「采用」「能够」→ 有的话手动改掉
- 检查原文有没有「核心」「关键」「显著」「较为」「提升」「揭示」「随着」→ 有的话删掉
- 检查原文是否还没出现「本文」「进行」「比较」「并且」「但是」→ 可选1个插入，如果已经有了就不要重复

【句长变化】
- 不要让所有句子差不多长。拆一句长的，合两句短的
- 至少制造出一个短句（10-20字）和一个长句（40-60字）
{role_hint}

【句式变化】
- 同一个动词或名词100字内不要重复
- 不要连续两句用相同词性的词开头
- 不要写"首先/其次/最后""随着...的发展""综上所述"
- 「对X进行Y」→ 直接写"Y了X"

【安全底线】
- 专业术语、数字、引用标记 [N] 不改
- 不改变原意，不添加原文没有的信息
- 括号必须配对完整
- 长度=原文的 80%-130%
- 不要用"我""我们"（除非原文已有）

---
## 输入
{input_text}

## 输出
只输出改写结果。"""

# L2: 段间协调 Prompt — 用于 C5.5C/T6.7C Stage L2 子 agent
LLM_INTER_PROMPT = """你是一个文本协调助手。以下是相邻的3个段落，可能已经过段内改写。你的任务是协调它们之间的关系，让三个段落读起来像同一个人的连续写作。

## 要改什么

【段首不要重复】
- 如果3段中有2段以上以相同的词开头（比如"本文""该""通过""从"），改掉其中至少1段开头
- 句首不要连着出现：本文、该、通过、同时、此外、基于、随着、针对

【段落之间要自然过渡】
- 段落之间靠内容逻辑推进，不要插入"首先/其次/最后"之类的序列词
- 如果上下文需要连接，可以用"实际上""说白了""从另一个角度看"

【篇幅控制】
- 如果某段明显比其他段长或短（偏离平均太多），适当回调
- 三段总字数不超过原文三段总字数的130%

【跨段去重】
- 相邻段落不要用同一句式重复开头（比如都"本文研究了…"）
- 如果相邻段落出现同样的罕见搭配，改掉

【安全底线】
- 专业术语、数字、引用标记 [N] 不改
- 不改变每段的意思
- 括号必须配对完整
- 不要用"我""我们"（除非原文已有）

---
## 输入
{three_paragraphs}

## 输出
只输出改写后的3段。格式示例：
段落1正文
（空行）
段落2正文
（空行）
段落3正文"""


def apply_llm_pass(text, intensity, api_func=None, role_hint=""):
    """LLM 层增强（单个段落接口）。

    Args:
        text: 输入段落
        intensity: 强度挡位
        api_func: callable(prompt) → 改写文本。若 None 则原样返回
        role_hint: 可选的角色提示字串（SENTENCE_ROLE_HINTS 之一）。不传则用空串
    Returns:
        (改写文本, 是否应用)
    """
    cfg = INTENSITY_CONFIG.get(intensity, INTENSITY_CONFIG["medium"])
    prob = cfg.get("llm_pass_prob", 0.0)

    if api_func is None or prob <= 0.0:
        return text, False
    if random.random() >= prob:
        return text, False

    if not role_hint:
        role_hint = SENTENCE_ROLE_HINTS[hash(text) % len(SENTENCE_ROLE_HINTS)]
    prompt = LLM_INTRA_PROMPT.format(input_text=text, role_hint=role_hint)

    result = api_func(prompt)

    if not result or not result.strip():
        return text, False
    if not is_well_formed(result):
        return text, False
    if len(result) > len(text) * 1.3 or len(result) < len(text) * 0.7:
        return text, False

    return result, True


# ═══════════════════════════════════════════════════════════════════════
# 主变换引擎
# ═══════════════════════════════════════════════════════════════════════

def inflate_text(text, intensity="medium"):
    cfg = INTENSITY_CONFIG[intensity]

    # ── 短段落降权 ──
    para_len = len(text)
    if para_len < 120:
        length_scale = max(0.3, para_len / 120)
    else:
        length_scale = 1.0

    def scaled_prob(key):
        return cfg[key] * length_scale

    transform_pipeline = [
        ("de_ai", lambda t: de_ai_connectives(t) if random.random() < scaled_prob("deai_prob") else (t, False)),
        ("expand", lambda t: apply_expand(t, scaled_prob("expand_prob"))),
        ("qualifier", lambda t: apply_qualifiers(t, scaled_prob("qualifier_prob"))),
        ("academic_variant", lambda t: apply_academic_variants(t, scaled_prob("academic_variant_prob"))),
        ("paraphrase", lambda t: apply_paraphrase(t, scaled_prob("paraphrase_prob"))),
        ("colloquial", lambda t: apply_colloquial(t, scaled_prob("colloquial_prob"))),
        ("conjunction", lambda t: apply_conjunctions(t, scaled_prob("conjunction_prob"))),
        ("asymmetric", lambda t: apply_asymmetric(t, scaled_prob("asymmetric_prob"))),
        ("abstract_subject", lambda t: apply_abstract_subject(t, scaled_prob("subject_abstract_prob"))),
        ("passive", lambda t: apply_passive(t, scaled_prob("passive_prob"))),
        ("reorder", lambda t: apply_reorder(t, scaled_prob("reorder_prob"))),
        ("filler", lambda t: apply_fillers(t, scaled_prob("filler_prob"))),
        ("sentence_mix", lambda t: apply_sentence_mix(t, scaled_prob("sentence_mix_prob"))),
        ("keyword_repeat", lambda t: apply_keyword_repeat(t, scaled_prob("keyword_repeat_prob"))),
        ("redundant", lambda t: apply_redundant(t, scaled_prob("redundant_prob"))),
        ("conclusion", lambda t: apply_conclusion(t, scaled_prob("conclusion_prob"))),
        ("cross_reorder", lambda t: apply_cross_reorder(t, scaled_prob("cross_reorder_prob"))),
        ("emphasis_shift", lambda t: apply_emphasis_shift(t, scaled_prob("emphasis_shift_prob"))),
        ("causal_variation", lambda t: apply_causal_variation(t, scaled_prob("causal_variation_prob"))),
    ]

    if intensity == "ultra":
        transform_pipeline.append(
            ("ultra_verbose", lambda t: apply_ultra_verbose(t, scaled_prob("ultra_verbose_prob")))
        )

    result = text
    max_hits = cfg.get("multi_transform", 1)
    hit_count = 0

    for name, func in transform_pipeline:
        if hit_count >= max_hits:
            break
        new_result, applied = func(result)
        if applied:
            result = new_result
            hit_count += 1

    # ── 结构性反向检查 ──
    if not is_well_formed(result) or not result.strip():
        return text
    return result


# ═══════════════════════════════════════════════════════════════════════
# 文本统计
# ═══════════════════════════════════════════════════════════════════════

def compute_text_stats(text_list):
    sentences = []
    for t in text_list:
        sentences.extend(re.split(r'(?<=[。！？])', t))
    sentences = [s.strip() for s in sentences if len(s.strip()) > 2]
    sent_lens = [len(s) for s in sentences]

    stats = {}
    stats["total_chars"] = sum(len(t) for t in text_list)
    stats["para_count"] = len(text_list)
    stats["para_lens"] = [len(t) for t in text_list]
    stats["para_mean"] = statistics.mean(stats["para_lens"]) if stats["para_lens"] else 0
    stats["para_std"] = statistics.stdev(stats["para_lens"]) if len(stats["para_lens"]) > 1 else 0

    stats["sent_count"] = len(sentences)
    stats["sent_mean"] = statistics.mean(sent_lens) if sent_lens else 0
    stats["sent_std"] = statistics.stdev(sent_lens) if len(sent_lens) > 1 else 0
    stats["sent_min"] = min(sent_lens) if sent_lens else 0
    stats["sent_max"] = max(sent_lens) if sent_lens else 0

    conn_count = sum(
        len(re.findall(r'(此外|因此|同时|总之|综上所述|值得注意的是|进一步而言|除此之外|然而|但是|所以|故而|因此)', t))
        for t in text_list
    )
    stats["connective_density"] = round(conn_count / max(stats["total_chars"], 1) * 100, 2)

    return stats


def print_stats(label, stats):
    print(f"\n  {label}:")
    print(f"    总字数: {stats['total_chars']}")
    print(f"    段落数: {stats['para_count']}")
    print(f"    段落均长: {stats['para_mean']:.1f} (σ={stats['para_std']:.1f})")
    print(f"    句子数: {stats['sent_count']}")
    print(f"    句均长: {stats['sent_mean']:.1f} (σ={stats['sent_std']:.1f})  min={stats['sent_min']} max={stats['sent_max']}")
    print(f"    连接词密度: {stats['connective_density']}%")


# ═══════════════════════════════════════════════════════════════════════
# AIGC 标红片段匹配引擎
# ═══════════════════════════════════════════════════════════════════════

def extract_search_keys(filepath):
    """从 AIGC 标红 txt 中提取搜索片段。

    鲁棒处理：
    - 空行分割
    - 无空行时按句号断句
    - 丢弃 <=8 字的片段
    - 去重
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # 规范化换行（仅 \r\n → \n），保留空行
    text = raw.replace('\r\n', '\n').strip()

    chunks = []
    # 策略1: 按空行（\n\n+）分割
    parts = re.split(r'\n\n+', text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        chunks = parts
    else:
        # 策略2: 无空行，按 。！？断句
        sents = re.split(r'(?<=[。！？])', text)
        # 相邻 2-3 句合并为一个搜索片段，提高唯一性
        buffer = []
        for s in sents:
            s = s.strip()
            if not s:
                continue
            buffer.append(s)
            if len(buffer) >= random.randint(2, 3):
                chunks.append(''.join(buffer))
                buffer = []
        if buffer:
            chunks.append(''.join(buffer))

    # 去重 + 过滤短片段
    seen = set()
    result = []
    for c in chunks:
        c = c.strip()
        if c and len(c) > 8 and c not in seen:
            seen.add(c)
            result.append(c)

    return result


def normalize_text(s):
    """正规化文本：去多余空白、正规化标点、统一全半角。"""
    # 全角字母数字 → 半角
    s = s.replace('（', '(').replace('）', ')').replace('：', ':')
    s = s.replace('，', ',').replace('；', ';').replace('！', '!').replace('？', '?')
    s = s.replace('【', '[').replace('】', ']').replace('《', '<').replace('》', '>')
    s = s.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    # 折叠空白
    s = re.sub(r'\s+', '', s)
    return s


def fuzzy_substring_match(key, text):
    """模糊子串匹配：使用 SequenceMatcher 判断近似匹配。

    key 中 >=80% 的字符按顺序出现在 text 中即视为匹配。
    处理 OCR 误字、隐形换行、多余空格、全半角差异。
    """
    a = normalize_text(key)
    b = normalize_text(text)

    if len(a) <= 2:
        return a in b

    # 快速排除：长度差太大（除非完全匹配）
    if len(a) > len(b) * 1.5:
        return a in b

    # 用 SequenceMatcher 找 key 在 text 中的最长匹配块
    matcher = difflib.SequenceMatcher(None, a, b)
    match = matcher.find_longest_match(0, len(a), 0, len(b))
    if match.size >= len(a) * 0.80:
        return True

    # 多块合并：分散但总计超过阈值
    total_matched = sum(
        block.size for block in matcher.get_matching_blocks()
        if block.size > 1
    )
    return total_matched >= len(a) * 0.80


def match_paragraphs(paragraphs, search_keys):
    """在段落列表中搜索匹配（精确 + 模糊两级）。

    返回 {para_index: [matched_key, ...]}
    仅包含命中的段落。
    """
    matches = {}
    used_keys = set()

    for i, para in enumerate(paragraphs):
        para_clean = para.strip()
        if not para_clean:
            continue

        # 预归一化段落文本
        para_norm = normalize_text(para_clean)

        for key in search_keys:
            key_clean = key.strip()
            if not key_clean:
                continue
            key_norm = normalize_text(key_clean)

            # 一级：精确子串匹配（归一化后）
            if key_norm in para_norm:
                if i not in matches:
                    matches[i] = []
                matches[i].append(key_clean)
                used_keys.add(key_clean)
                continue

            # 二级：模糊子串匹配
            if fuzzy_substring_match(key_norm, para_norm):
                if i not in matches:
                    matches[i] = []
                matches[i].append(key_clean)
                used_keys.add(key_clean)
                continue

    return matches, used_keys


def print_match_report(matches, search_keys, paragraphs):
    """打印匹配报告。"""
    total_keys = len(search_keys)
    used_keys = set()
    for keys in matches.values():
        used_keys.update(keys)

    print(f"\n  AIGC 标红匹配报告:")
    print(f"  从标红文本提取到 {total_keys} 个搜索片段")
    print(f"  匹配到 {len(matches)} 个段落:")

    for idx in sorted(matches.keys()):
        preview = paragraphs[idx][:50] if idx < len(paragraphs) else "(超出范围)"
        keys_str = ', '.join(f'"{k[:30]}..."' for k in matches[idx])
        print(f"    第{idx}段: {preview}...")
        print(f"           命中: {keys_str}")

    unused = [k for k in search_keys if k not in used_keys]
    if unused:
        print(f"  未匹配的 {len(unused)} 个片段:")
        for k in unused:
            print(f"    - {k[:50]}...")
    else:
        print(f"  所有搜索片段均已匹配。")


# ═══════════════════════════════════════════════════════════════════════
# docx 处理
# ═══════════════════════════════════════════════════════════════════════

def inflate_docx(input_path, output_path, intensity="medium", dry_run=False, show_stats=False,
                 aigc_flags_path=None):
    global _used_fillers, _used_fragments
    _used_fillers.clear()  # 重置全局状态
    _used_fragments.clear()

    cfg = INTENSITY_CONFIG[intensity]
    doc = Document(input_path)

    # ── AIGC 靶向匹配 ──
    target_indices = None
    aigc_matched_indices = None
    if aigc_flags_path:
        if not os.path.exists(aigc_flags_path):
            print(f"AIGC 标红文件不存在: {aigc_flags_path}")
            return
        search_keys = extract_search_keys(aigc_flags_path)
        # 收集所有段落文本用于匹配
        all_paras = [p.text.strip() for p in doc.paragraphs]
        matches, used_keys = match_paragraphs(all_paras, search_keys)
        target_indices = set(matches.keys())
        aigc_matched_indices = sorted(target_indices)
        print_match_report(matches, search_keys, all_paras)

        # 写入 .meta.json 供 stage 层 LLM 子 agent 使用
        meta_path = os.path.splitext(output_path)[0] + ".meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "aigc_target_indices": aigc_matched_indices,
                "total_paragraphs": len(all_paras),
                "targeted_count": len(aigc_matched_indices),
            }, f, ensure_ascii=False)
        print(f"  元数据已写入: {meta_path}")

    total_para_chars = 0
    modified_count = 0
    change_log = []

    before_texts = []
    after_texts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if is_heading_text(text):
            before_texts.append(text)
            after_texts.append(text)
            continue
        if is_reference_line(text):
            before_texts.append(text)
            after_texts.append(text)
            continue
        if is_short_label(text):
            before_texts.append(text)
            after_texts.append(text)
            continue

        # ── AIGC 靶向模式：仅注水匹配段落 ──
        if target_indices is not None:
            para_index = len(before_texts)
            if para_index not in target_indices:
                before_texts.append(text)
                after_texts.append(text)
                continue

        total_para_chars += len(text)
        before_texts.append(text)

        new_text = inflate_text(text, intensity)
        after_texts.append(new_text)

        if new_text != text:
            modified_count += 1
            change_log.append((text[:40], new_text[:60], len(new_text) - len(text)))
            if not dry_run and para.runs:
                para.runs[0].text = new_text
                for r in para.runs[1:]:
                    r.text = ""

    if intensity == "ultra" and not dry_run:
        para_texts = [p.text for p in doc.paragraphs if p.text.strip()]
        merged = apply_paragraph_merge(para_texts, cfg["paragraph_merge_prob"])
        if merged != para_texts:
            idx = 0
            for para in doc.paragraphs:
                if not para.text.strip():
                    continue
                if is_heading_text(para.text.strip()):
                    continue
                if is_reference_line(para.text.strip()):
                    continue
                if is_short_label(para.text.strip()):
                    continue
                if idx < len(merged) and merged[idx]:
                    if para.runs:
                        para.runs[0].text = merged[idx]
                        for r in para.runs[1:]:
                            r.text = ""
                idx += 1

    total_chars = sum(len(p.text) for p in doc.paragraphs)

    if show_stats or dry_run:
        before_stats = compute_text_stats(before_texts)
        if dry_run:
            print_stats("变换前", before_stats)
            print(f"\n  [DRY RUN] 强度={intensity}")
            print(f"  预计修改: ~{modified_count} 段")
            print(f"  预计膨胀: ~{int(total_para_chars * 0.2)}-{int(total_para_chars * 0.8)} 字")
        else:
            after_stats = compute_text_stats(after_texts)
            print_stats("变换前", before_stats)
            print_stats("变换后", after_stats)
            print(f"\n  Δ 总字数: {after_stats['total_chars'] - before_stats['total_chars']:+d}")
            print(f"  Δ 句长方差: {after_stats['sent_std'] - before_stats['sent_std']:+.1f}")
            print(f"  Δ 连接词密度: {after_stats['connective_density'] - before_stats['connective_density']:+.2f}%")

    if dry_run:
        return

    if modified_count > 0:
        doc.save(output_path)
        print(f"\nOK - 已生成: {output_path}")
        print(f"  修改段落: {modified_count}")
        print(f"  总字符: {total_chars}")
        print(f"\n变换示例（前5条）:")
        for before, after, delta in change_log[:5]:
            print(f"  +{delta:+d}字: {before}... → {after}...")
    else:
        print("未做任何修改。")


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="论文一键注水 v4 — 写作风格扰动引擎")
    parser.add_argument("input", help="输入 .docx 路径")
    parser.add_argument("--intensity", choices=["light", "medium", "heavy", "ultra"],
                        default="medium", help="注水强度 (默认 medium)")
    parser.add_argument("--output", help="输出路径（默认 input_inflated.docx）")
    parser.add_argument("--dry-run", action="store_true", help="只预览统计，不改写")
    parser.add_argument("--stats", action="store_true", help="打印变换前后文本统计")
    parser.add_argument("--aigc-flags", type=str, default=None,
                        help="AIGC 检测标红片段 txt 路径（仅注水匹配段落）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"文件不存在: {args.input}")
        return

    output = args.output or args.input.replace(".docx", "_inflated.docx")
    if output == args.input:
        output = args.input.replace(".docx", "_inflated.docx")

    inflate_docx(args.input, output, args.intensity, args.dry_run, args.stats,
                 aigc_flags_path=args.aigc_flags)


if __name__ == "__main__":
    main()
