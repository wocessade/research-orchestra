"""
词级同义替换模块 — 三层防护架构

L1 频率门：仅替换全文出现 >= threshold 次的词
L2 学科软过滤：根据 discipline 匹配 #通/#偏文/#偏理 tag
L3 每词替换上限：每个 key 词在全文中最多用 max_variants 种变体

与 inflate_paper.py 解耦，可独立测试。
"""

import re
import os
import random
import sys
from collections import Counter

from docx import Document
from vocab_diversity_data import VOCAB_SYNONYMS as _RAW_VOCAB


# ── 加载时解析 "text #tag" 格式 ──

def _parse_vocab(raw):
    """解析词表：{"key": ["text #tag", ...]} → {"key": [(text, tag), ...]}"""
    parsed = {}
    for key, variants in raw.items():
        entries = []
        for v in variants:
            if v == "#DELETE":
                entries.append(("#DELETE", "#DELETE"))
                continue
            m = re.match(r'^(.+?)\s+(#\S+)$', v)
            if m:
                entries.append((m.group(1).strip(), m.group(2)))
            else:
                entries.append((v.strip(), "#通"))
        parsed[key] = entries
    return parsed


VOCAB = _parse_vocab(_RAW_VOCAB)

# discipline → 允许的 tag 集合
DISCIPLINE_TAGS = {
    "general":    {"#通"},
    "humanities": {"#通", "#偏文"},
    "stem":       {"#通", "#偏理"},
    "any":        {"#通", "#偏文", "#偏理", "#DELETE"},
}


# ── ReplacementTracker ──

class ReplacementTracker:
    """追踪每个 key 词在全文中已被替换的次数和变体集合"""

    def __init__(self, max_variants=2):
        self.max_variants = max_variants
        self.used = {}    # key_word → set of variant texts used
        self.counts = {}  # key_word → total replacement count
        self.total_replacements = 0  # 总替换数
        self.l1_skipped = 0   # 频率门过滤数
        self.l2_skipped = 0   # 学科过滤数
        self.l3_skipped = 0   # 上限过滤数
        self.attempted = 0    # 尝试替换次数

    def can_replace(self, key_word):
        return len(self.used.get(key_word, set())) < self.max_variants

    def get_unused_variants(self, key_word, candidates):
        """从 candidates 中返回未被使用过的变体；若都已用过则返回全部"""
        used_set = self.used.get(key_word, set())
        unused = [(t, tag) for t, tag in candidates if t not in used_set]
        return unused if unused else candidates

    def mark_replaced(self, key_word, variant_text):
        self.used.setdefault(key_word, set()).add(variant_text)
        self.counts[key_word] = self.counts.get(key_word, 0) + 1
        self.total_replacements += 1


# ── build_freq_map ──

def build_freq_map(paragraphs):
    """全文档词频统计，仅对 VOCAB 中存在的 key 词计数"""
    counter = Counter()
    full_text = "\n".join(paragraphs)
    for key in VOCAB:
        # 用正则匹配完整词（非子串）
        n = len(re.findall(re.escape(key), full_text))
        if n > 0:
            counter[key] = n
    return dict(counter)


# ── apply_vocab_diversity ──

def apply_vocab_diversity(text, freq_map, tracker, prob,
                          threshold=5, discipline="general"):
    """单段落的词级同义替换。

    Args:
        text: 当前段落文本
        freq_map: build_freq_map() 的输出
        tracker: ReplacementTracker 实例
        prob: 触发概率 (0.0~1.0)
        threshold: L1 频率门阈值（仅替换 freq ≥ threshold 的词）
        discipline: "general" | "humanities" | "stem" | "any"

    Returns:
        (modified_text, applied: bool)
    """
    if random.random() >= prob:
        return text, False

    allowed_tags = DISCIPLINE_TAGS.get(discipline, DISCIPLINE_TAGS["general"])

    # 找出所有在文本中出现的 VOCAB key
    present_keys = []
    for key in VOCAB:
        if key in text:
            present_keys.append(key)

    if not present_keys:
        return text, False

    # 构建候选列表：(key, position, eligible_variants)
    candidates = []
    for key in present_keys:
        freq = freq_map.get(key, 0)

        # L1: 频率门
        if freq < threshold:
            tracker.l1_skipped += 1
            continue

        # L2: 学科过滤 — 仅保留 tag 匹配的变体
        variants = VOCAB[key]
        eligible = [(t, tag) for t, tag in variants if tag in allowed_tags]
        if not eligible:
            tracker.l2_skipped += 1
            continue

        # L3: 变体数上限
        if not tracker.can_replace(key):
            tracker.l3_skipped += 1
            continue

        # 找到 key 在文本中的位置
        pos = text.find(key)
        if pos >= 0:
            candidates.append((key, pos, eligible))

    if not candidates:
        return text, False

    # 随机选一个候选词做替换
    key, pos, eligible = random.choice(candidates)
    tracker.attempted += 1

    # 优先选未用过的变体
    unused = tracker.get_unused_variants(key, eligible)
    chosen_text, chosen_tag = random.choice(unused)

    # 执行替换（仅替换找到位置的第一个匹配）
    new_text = text[:pos] + chosen_text + text[pos + len(key):]

    tracker.mark_replaced(key, chosen_text)
    return new_text, True


# ── 便捷函数 ──

def get_vocab_stats():
    """返回词表统计信息"""
    total_keys = len(VOCAB)
    total_variants = sum(len(v) for v in VOCAB.values())
    tag_counts = Counter()
    for entries in VOCAB.values():
        for _, tag in entries:
            tag_counts[tag] += 1
    return {
        "total_keys": total_keys,
        "total_variants": total_variants,
        "tag_distribution": dict(tag_counts),
    }


def get_tracker_stats(tracker):
    """返回 tracker 统计信息（用于 --stats 输出）"""
    return {
        "total_replacements": tracker.total_replacements,
        "unique_keys_touched": len(tracker.used),
        "attempted": tracker.attempted,
        "l1_skipped": tracker.l1_skipped,
        "l2_skipped": tracker.l2_skipped,
        "l3_skipped": tracker.l3_skipped,
    }


# ── CLI ──

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="词级同义替换 — 降AI词汇多样性 (L1频率门 + L2学科过滤 + L3变体上限)")
    parser.add_argument("input", help="输入 .docx 路径")
    parser.add_argument("--output", help="输出路径 (默认覆盖输入)")
    parser.add_argument("--discipline", choices=["general", "humanities", "stem", "any"],
                        default="general", help="学科方向 (默认 general)")
    parser.add_argument("--threshold", type=int, default=5,
                        help="L1 频率门阈值 (默认 5)")
    parser.add_argument("--max-variants", type=int, default=2,
                        help="L3 每词最大变体数 (默认 2)")
    parser.add_argument("--prob", type=float, default=0.5,
                        help="每段触发概率 (默认 0.5)")
    parser.add_argument("--stats", action="store_true",
                        help="打印替换统计")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"文件不存在: {args.input}")
        sys.exit(1)

    output = args.output or args.input
    doc = Document(args.input)

    # ── 词频预扫描 ──
    all_paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    freq_map = build_freq_map(all_paras)
    tracker = ReplacementTracker(max_variants=args.max_variants)

    # ── 逐段替换 ──
    modified_count = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        new_text, applied = apply_vocab_diversity(
            text, freq_map, tracker,
            prob=args.prob,
            threshold=args.threshold,
            discipline=args.discipline,
        )
        if applied:
            modified_count += 1
            if para.runs:
                para.runs[0].text = new_text
                for r in para.runs[1:]:
                    r.text = ""

    # ── 统计 ──
    if args.stats:
        vs = get_tracker_stats(tracker)
        high_freq = {k: v for k, v in freq_map.items() if v >= args.threshold}
        print(f"词级替换统计:")
        print(f"  词表大小: {len(VOCAB)} 词条")
        print(f"  高频词命中: {len(freq_map)} 个 (≥{args.threshold}次: {len(high_freq)} 个)")
        print(f"  总替换数: {vs['total_replacements']}")
        print(f"  涉及词数: {vs['unique_keys_touched']}")
        print(f"  修改段落: {modified_count}")
        print(f"  L1 频率门过滤: {vs['l1_skipped']}")
        print(f"  L2 学科过滤: {vs['l2_skipped']}")
        print(f"  L3 上限过滤: {vs['l3_skipped']}")
        if vs['unique_keys_touched'] > 0:
            print(f"\n  已替换词汇:")
            for key in sorted(tracker.used.keys()):
                variants_used = tracker.used[key]
                print(f"    {key} → {', '.join(variants_used)} "
                      f"({tracker.counts[key]}次)")

    # ── 保存 ──
    if modified_count > 0:
        doc.save(output)
        print(f"\nOK - 已保存: {output}  (修改 {modified_count} 段)")
    else:
        print("未做任何修改。")


if __name__ == "__main__":
    main()
