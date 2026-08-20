"""
一次性脚本：合并 command.txt 中多个重叠的词汇同义替换 dict，
输出为 vocab_diversity_data.py — 单一权威词表。

用法:
  python merge_vocab.py <input.txt> [output.py]

默认输出: 同目录下的 vocab_diversity_data.py
"""

import re, sys, os
from collections import defaultdict

def parse_command_txt(filepath):
    """解析 command.txt，提取所有 dict 变量为 {key: [(text, tag), ...]}"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 找所有 dict 变量块: NAME = { ... }
    dict_blocks = re.findall(
        r'\b([A-Z_]+[A-Z_]*)\s*=\s*\{(.*?)\n\}',
        content, re.DOTALL
    )

    all_entries = defaultdict(list)  # key → [(variant_text, tag)]
    var_counts = {}  # 每个变量的条目数

    for var_name, body in dict_blocks:
        count = 0
        # 匹配每个条目: "key": ["v1 #tag", "v2 #tag", ...]
        entries = re.findall(
            r'"([^"]+)"\s*:\s*\[(.*?)\]',
            body, re.DOTALL
        )
        for key, values_str in entries:
            # 提取各个值（去除引号）
            values = re.findall(r'"([^"]*)"', values_str)
            for v in values:
                v = v.strip()
                if not v:
                    continue
                # 分离 tag
                if v == "#DELETE":
                    all_entries[key].append(("#DELETE", "#DELETE"))
                else:
                    # 匹配 "text #tag" 或 "text#tag"
                    # 规范化: #理→#偏理, #文→#偏文
                    tag_norm = {"通": "通", "偏文": "偏文", "偏理": "偏理",
                                "文": "偏文", "理": "偏理", "DELETE": "DELETE"}
                    m = re.match(r'^(.+?)\s*#(通|偏文|偏理|文|理|DELETE)$', v)
                    if m:
                        tag = tag_norm.get(m.group(2), m.group(2))
                        all_entries[key].append((m.group(1).strip(), f"#{tag}"))
                    else:
                        # 无 tag，默认 #通
                        all_entries[key].append((v.strip(), "#通"))
                count += 1
        var_counts[var_name] = count

    return all_entries, var_counts


def merge_entries(entries):
    """合并去重：同一 (text, tag) 只保留一次；tag 不同的保留全部"""
    seen = set()
    merged = []
    for text, tag in entries:
        key = (text, tag)
        if key not in seen:
            seen.add(key)
            merged.append((text, tag))
    return merged


def count_categories(all_entries):
    """统计各类词条数"""
    n_verbs = n_nouns = n_connectives = n_adverbs = n_patterns = 0
    for key, entries in all_entries.items():
        # 简单启发式：看第一个 variant 的 tag 或 key 本身特征
        total = len(entries)
        if any(t == "#DELETE" for _, t in entries):
            n_connectives += 1
        elif len(key) >= 8 or any(len(text) >= 8 for text, _ in entries):
            n_patterns += 1
        else:
            # 默认按 key 特征分类（粗略）
            n_verbs += 1  # 大部分是动词
    return {
        "total_keys": len(all_entries),
        "total_variants": sum(len(v) for v in all_entries.values()),
    }


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not input_path or not os.path.exists(input_path):
        print(f"用法: python merge_vocab.py <command.txt> [output.py]")
        print(f"输入文件不存在: {input_path}")
        sys.exit(1)

    output_path = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.path.dirname(__file__) or ".", "vocab_diversity_data.py")

    print(f"解析: {input_path}")
    all_entries, var_counts = parse_command_txt(input_path)

    print(f"\n找到 {len(var_counts)} 个 dict 变量:")
    for name, count in sorted(var_counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count} 条")

    # 合并
    merged = {}
    for key, entries in all_entries.items():
        merged[key] = merge_entries(entries)

    stats = count_categories(merged)
    print(f"\n合并后:")
    print(f"  总词条数(key): {stats['total_keys']}")
    print(f"  总变体数(value): {stats['total_variants']}")

    # 检测重复冲突（同一 key 在不同 dict 中出现）
    duplicate_check = defaultdict(list)
    # 重新扫描原始文件，记录每个 key 来自哪些 dict
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
    dict_blocks = re.findall(r'\b([A-Z_]+[A-Z_]*)\s*=\s*\{(.*?)\n\}', content, re.DOTALL)
    for var_name, body in dict_blocks:
        keys_in_block = re.findall(r'"([^"]+)"\s*:', body)
        for k in keys_in_block:
            duplicate_check[k].append(var_name)

    dupes = {k: v for k, v in duplicate_check.items() if len(v) > 1}
    if dupes:
        print(f"\n  重复 key（出现在多个 dict 中）: {len(dupes)} 个")
        for k, sources in list(dupes.items())[:10]:
            print(f"    {k}: {sources}")

    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 学术词汇多样性词表 — 自动合并自 command.txt\n")
        f.write(f"# 来源 {len(var_counts)} 个 dict 变量，合并后 {stats['total_keys']} 个词条\n")
        f.write("# 格式: \"原文\" → [(变体文本, 标签)]\n")
        f.write("# 标签: #通 (通用), #偏文 (偏文科), #偏理 (偏理科), #DELETE (可删除)\n\n")
        f.write("VOCAB_SYNONYMS = {\n")

        for key in sorted(merged.keys()):
            variants = merged[key]
            # 格式化为字符串列表
            parts = []
            for text, tag in variants:
                if tag == "#DELETE":
                    parts.append(f'"#DELETE"')
                else:
                    parts.append(f'"{text} {tag}"')
            f.write(f'    "{key}": [{", ".join(parts)}],\n')

        f.write("}\n")

    print(f"\n输出: {output_path}")
    print("完成。")


if __name__ == "__main__":
    main()
