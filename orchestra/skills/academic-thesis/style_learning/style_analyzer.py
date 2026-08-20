"""
文风分析器 — StyleAnalyzer

从文本文件中提取 Style Profile（四维风格特征）。
纯文本统计实现，不需要 NLP 依赖库。
"""

import re
import json
import os
from pathlib import Path
from typing import Optional

class StyleAnalyzer:
    """从文本提取四维风格特征（句式/词汇/结构/引用）"""

    def __init__(self):
        # 常用中文停用词
        self.stopwords = set("的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 他 她 它 们 那 些 为 以 能 但 而 从 被 把 对 与 或 等 之 所 其 中 年 月 日".split())
        # 连词
        self.conjunctions = ["然而", "但是", "因此", "所以", "从而", "不过", "而且", "此外", "另外", "总之", "换言之", "换言之"]
        # 口语化词
        self.colloquial = ["其实", "真的", "特别", "非常", "很", "挺", "有点", "有点儿"]

    def extract(self, text: str) -> dict:
        """提取完整 Style Profile"""
        sentences = self._split_sentences(text)
        paragraphs = self._split_paragraphs(text)

        return {
            "sentence": self._analyze_sentence(sentences),
            "vocabulary": self._analyze_vocabulary(text, sentences),
            "structure": self._analyze_structure(text, paragraphs, sentences),
            "citation": self._analyze_citations(text, sentences)
        }

    def diff(self, profile_a: dict, profile_b: dict) -> list:
        """对比两个 Style Profile，返回差异建议列表"""
        suggestions = []

        # 句式对比
        a_len = profile_a.get("sentence", {}).get("avg_length", 0)
        b_len = profile_b.get("sentence", {}).get("avg_length", 0)
        if a_len and b_len and abs(a_len - b_len) > 3:
            suggestions.append({
                "dimension": "句式",
                "metric": "平均句长",
                "current": a_len,
                "target": b_len,
                "suggestion": f"你的平均句长{a_len:.0f}字，目标{b_len:.0f}字——建议{'拆分' if a_len > b_len else '合并'}多字句"
            })

        # 引用密度对比
        a_cite = profile_a.get("citation", {}).get("density_per_1k", 0)
        b_cite = profile_b.get("citation", {}).get("density_per_1k", 0)
        if a_cite and b_cite and abs(a_cite - b_cite) > 0.5:
            suggestions.append({
                "dimension": "引用",
                "metric": "引用密度",
                "current": a_cite,
                "target": b_cite,
                "suggestion": f"你的引用密度{a_cite:.1f}次/千字，目标{b_cite:.1f}次/千字——建议{'补充' if a_cite < b_cite else '减少'}引用"
            })

        # 主动被动对比
        a_ap = profile_a.get("sentence", {}).get("active_passive_ratio", 0)
        b_ap = profile_b.get("sentence", {}).get("active_passive_ratio", 0)
        if a_ap and b_ap and abs(a_ap - b_ap) > 0.15:
            suggestions.append({
                "dimension": "句式",
                "metric": "主动语态比例",
                "current": a_ap,
                "target": b_ap,
                "suggestion": f"你的主动语态比例{a_ap:.0%}，目标{b_ap:.0%}——建议{'转为主动' if a_ap < b_ap else '使用被动'}"
            })

        return suggestions

    def save_profile(self, profile: dict, output_path: str):
        """保存 Style Profile 到 JSON 文件"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def load_profile(self, path: str) -> Optional[dict]:
        """从 JSON 文件加载 Style Profile"""
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _split_sentences(self, text: str) -> list:
        """分句"""
        text = re.sub(r'\s+', ' ', text)
        sentences = re.split(r'(?<=[。！？.!?])', text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def _split_paragraphs(self, text: str) -> list:
        """分段"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if len(p.strip()) > 20]

    def _tokenize(self, text: str) -> list:
        """简单分词（按字符+常见词拆分）"""
        # 使用简单的正则匹配中文词和英文词
        tokens = re.findall(r'[一-鿿]{2,4}|[a-zA-Z]{2,}', text)
        return [t for t in tokens if t.lower() not in self.stopwords]

    def _analyze_sentence(self, sentences: list) -> dict:
        if not sentences:
            return {"avg_length": 0, "length_distribution": {}, "active_passive_ratio": 0}
        lengths = [len(s) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        short = sum(1 for l in lengths if l < 15) / len(lengths) if lengths else 0
        medium = sum(1 for l in lengths if 15 <= l <= 30) / len(lengths) if lengths else 0
        long_ = sum(1 for l in lengths if l > 30) / len(lengths) if lengths else 0

        # 简单主动/被动检测：含"被"字的句子占比
        passive = sum(1 for s in sentences if "被" in s) / len(sentences) if sentences else 0

        return {
            "avg_length": round(avg_len, 1),
            "length_distribution": {"short": round(short, 2), "medium": round(medium, 2), "long": round(long_, 2)},
            "active_passive_ratio": round(1 - passive, 2)
        }

    def _analyze_vocabulary(self, text: str, sentences: list) -> dict:
        tokens = self._tokenize(text)
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_freq = sorted(freq.items(), key=lambda x: -x[1])

        total_tokens = len(tokens)
        colloq_count = sum(1 for c in self.colloquial if c in text)
        en_tokens = sum(1 for t in tokens if re.match(r'[a-zA-Z]', t))

        return {
            "top_30": [w for w, _ in sorted_freq[:30]],
            "term_density": round(len(tokens) / max(len(text), 1), 2),
            "colloquial_rate": round(colloq_count / max(len(sentences), 1), 3),
            "en_mix_rate": round(en_tokens / max(total_tokens, 1), 3)
        }

    def _analyze_structure(self, text: str, paragraphs: list, sentences: list) -> dict:
        if not paragraphs:
            return {}
        para_sents = [len(self._split_sentences(p)) for p in paragraphs]
        mean = sum(para_sents) / len(para_sents) if para_sents else 0
        std = (sum((x - mean) ** 2 for x in para_sents) / len(para_sents)) ** 0.5 if para_sents else 0

        return {
            "para_length_mean": round(mean, 1),
            "para_length_std": round(std, 1),
            "reasoning_pattern": "deductive"
        }

    def _analyze_citations(self, text: str, sentences: list) -> dict:
        """分析引用模式"""
        # 匹配 (Author, Year) 和 Author (Year) 模式
        parenthetical = len(re.findall(r'\([^)]*\d{4}[^)]*\)', text))
        narrative = len(re.findall(r'[一-鿿]+\(?\d{4}\)?', text))
        total_citations = parenthetical + narrative

        total_chars = len(text)
        density = (total_citations / max(total_chars, 1)) * 1000

        return {
            "density_per_1k": round(density, 2),
            "narrative_ratio": round(narrative / max(total_citations, 1), 2),
            "parenthetical_ratio": round(parenthetical / max(total_citations, 1), 2)
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python style_analyzer.py <输入文件> [输出路径]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    analyzer = StyleAnalyzer()
    profile = analyzer.extract(text)

    if output_path:
        analyzer.save_profile(profile, output_path)
        print(f"Style Profile 已保存到: {output_path}")
    else:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
