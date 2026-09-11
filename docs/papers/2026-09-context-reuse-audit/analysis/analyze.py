"""Reuse-audit experiment analysis.

Inputs (all produced by the 2026-09-11 overnight run):
  data/channel_a/*.json   usage.json per dsh agent-harness call (17 calls)
  data/channel_a_runs.jsonl  run ledger records (tags, conditions, timings)
  data/channel_b_probe.json  raw-API probe results (8 calls)

Outputs:
  out/tables.md   markdown tables used verbatim in the paper
  out/summary.json
  out/fig_hit.pdf / fig_hit.png
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CH_A = ROOT / "data" / "channel_a"
CH_B = ROOT / "data" / "channel_b_probe.json"
RUNS = ROOT / "data" / "channel_a_runs.jsonl"
OUT = ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)


def load_channel_a():
    records = []
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    rows = []
    for record in records:
        usage_path = CH_A / f"{record['run_id']}.json"
        usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else {}
        rows.append(
            {
                "tag": record["tag"],
                "condition": record["condition"],
                "doc": record["doc"],
                "tier": record["tier"],
                "seconds": record.get("seconds"),
                "state": record.get("final_state"),
                "cost": (record.get("result") or {}).get("actual_cost_cny"),
                "input_tokens": usage.get("input_tokens"),
                "cache_read_tokens": usage.get("cache_read_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
        )
    return rows


def load_channel_b():
    return json.loads(CH_B.read_text(encoding="utf-8"))


def char_bigrams(text: str) -> set[str]:
    cleaned = "".join(ch for ch in text if not ch.isspace())
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def channel_a_table(rows) -> str:
    lines = [
        "| 调用 | 条件 | 层 | 输入tokens | 缓存命中tokens | 输出tokens | 时延(s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['tag']} | {row['condition']} | {row['tier']} | "
            f"{row['input_tokens']} | {row['cache_read_tokens']} | "
            f"{row['output_tokens']} | {row['seconds']} |"
        )
    hits = [row["cache_read_tokens"] or 0 for row in rows]
    lines.append("")
    lines.append(f"命中 tokens 合计：{sum(hits)}／{len(rows)} 次调用（每次调用输入均 ≈ 16.4k tokens）。")
    return "\n".join(lines)


def channel_b_table(rows) -> str:
    lines = [
        "| 调用 | 条件 | 模型 | 输入tokens | 命中tokens | 未命中tokens | 命中率 | 时延(ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        prompt = row["prompt_tokens"] or 0
        hit = row["cache_hit_tokens"] or 0
        ratio = f"{hit / prompt:.1%}" if prompt else "—"
        lines.append(
            f"| {row['tag']} | {row['condition']} | {row['model']} | {prompt} | "
            f"{hit} | {row['cache_miss_tokens']} | {ratio} | {row['latency_ms']:.0f} |"
        )
    return "\n".join(lines)


def detector_evaluation(rows):
    """Threshold rule: a call reuses a previously seen context iff cache_hit > 0."""
    same_doc = {"s2", "s3", "s5", "s6", "s8"}
    cross_tier = {"s7"}
    different = {"s4"}
    results = []
    for row in rows:
        if row["tag"] == "s1":
            continue
        hit = row["cache_hit_tokens"] or 0
        predicted_reuse = hit > 0
        if row["tag"] in same_doc:
            expected = True
        elif row["tag"] in cross_tier:
            expected = False  # same document text, different model: cache does not carry over
        else:
            expected = False
        results.append(
            {
                "tag": row["tag"],
                "condition": row["condition"],
                "expected_reuse": expected,
                "predicted_reuse": predicted_reuse,
                "correct": expected == predicted_reuse,
                "hit": hit,
            }
        )
    correct = sum(1 for item in results if item["correct"])
    return results, correct, len(results)


def output_similarity(rows):
    answers = {
        row["tag"]: (row.get("answer") or "")
        for row in rows
        if row.get("answer")
    }
    pairs = []
    tags = list(answers)
    for i, left in enumerate(tags):
        for right in tags[i + 1 :]:
            pairs.append(
                {
                    "pair": f"{left}-{right}",
                    "bigram_jaccard": round(
                        jaccard(char_bigrams(answers[left]), char_bigrams(answers[right])), 3
                    ),
                }
            )
    return {"answers": len(answers), "pairs": pairs}


CONDITIONS = {
    "same-prefix-2nd": "reuse",
    "same-prefix-3rd": "reuse",
    "verbatim-repeat": "reuse",
    "interleaved-return": "reuse",
    "flash-after-pro": "reuse",
    "cross-tier-pro": "cross-tier",
    "miss-anchor": "control",
    "diff-doc-baseline": "control",
}
CONDITION_STYLE = {
    "reuse": ("#4C72B0", "same-document reuse"),
    "cross-tier": ("#DD8452", "cross-tier call"),
    "control": ("#C44E52", "negative control"),
}


def figure(rows, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    labels = [row["tag"] for row in rows]
    hits = [row["cache_hit_tokens"] or 0 for row in rows]
    kinds = [CONDITIONS[row["condition"]] for row in rows]
    top = max(hits) * 1.25

    fig, ax = plt.subplots(figsize=(6.4, 2.8), dpi=200)
    ax.axhline(0, color="#B0B0B0", linewidth=0.8, zorder=1)
    for index, (hit, kind) in enumerate(zip(hits, kinds)):
        color = CONDITION_STYLE[kind][0]
        # 竖线画长度、圆点标位置：命中为 0 时线段退化，靠 y=0 上的圆点保持可见
        ax.vlines(index, 0, hit, color=color, linewidth=2.4, zorder=2)
        ax.plot(index, hit, "o", color=color, markersize=7, zorder=3)
        ax.text(index, hit + top * 0.06, str(hit), ha="center", fontsize=8, color="#333333")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("cache-hit tokens")
    ax.set_xlabel("raw-API call (in execution order)")
    ax.set_ylim(-top * 0.12, top)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    handles = [
        Line2D([], [], color=color, marker="o", markersize=6, label=label)
        for _, (color, label) in CONDITION_STYLE.items()
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def mechanism_evidence():
    """Two dsh runs' system prompts: where do they diverge?"""
    left = (ROOT / "data" / "sys-a1.txt").read_text(encoding="utf-8")
    right = (ROOT / "data" / "sys-e1.txt").read_text(encoding="utf-8")
    common = 0
    for a, b in zip(left, right):
        if a != b:
            break
        common += 1
    return {
        "prompt_chars": [len(left), len(right)],
        "common_prefix_chars": common,
        "divergence_context": left[max(0, common - 80) : common + 80].replace("\n", "\\n"),
        "note": "除运行专属产物路径外，两次运行的请求系统提示逐字节相同",
    }


def main() -> None:
    channel_a = load_channel_a()
    channel_b = load_channel_b()
    results, correct, total = detector_evaluation(channel_b)
    similarity = output_similarity(channel_b)
    mechanism = mechanism_evidence()
    ttl_path = ROOT / "data" / "channel_b_ttl.json"
    ttl = json.loads(ttl_path.read_text(encoding="utf-8")) if ttl_path.exists() else None

    summary = {
        "channel_a_calls": len(channel_a),
        "channel_a_cache_hits_total": sum(row["cache_read_tokens"] or 0 for row in channel_a),
        "channel_a_input_tokens_mean": round(
            sum(row["input_tokens"] or 0 for row in channel_a) / max(len(channel_a), 1), 1
        ),
        "channel_b_same_doc_hits": [row["cache_hit_tokens"] for row in channel_b if row["tag"] in {"s2", "s3", "s5", "s6", "s8"}],
        "channel_b_diff_doc_hits": [row["cache_hit_tokens"] for row in channel_b if row["tag"] in {"s4"}],
        "channel_b_cross_tier_hits": [row["cache_hit_tokens"] for row in channel_b if row["tag"] == "s7"],
        "detector": {"correct": correct, "total": total, "results": results},
        "output_similarity": similarity,
        "mechanism": mechanism,
        "ttl_probe": ttl,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    tables = []
    tables.append("## 表1 通道A（dsh agent 通道）17 次受控调用\n")
    tables.append(channel_a_table(channel_a))
    tables.append("\n## 表2 通道B（裸 API 通道）8 次受控调用\n")
    tables.append(channel_b_table(channel_b))
    tables.append("\n## 判定规则评估（通道B）\n")
    tables.append(f"规则：`cache_hit_tokens > 0` ⇒ 判定为复用既有上下文。准确 {correct}/{total}。")
    for item in results:
        tables.append(
            f"- {item['tag']} ({item['condition']}): 期望={'复用' if item['expected_reuse'] else '不复用'}"
            f"，判定={'复用' if item['predicted_reuse'] else '不复用'}，命中={item['hit']}"
        )
    tables.append("\n## 输出文本相似度基线（字符二元组 Jaccard）\n")
    for pair in similarity["pairs"]:
        tables.append(f"- {pair['pair']}: {pair['bigram_jaccard']}")
    tables.append("\n## 机制证据：两次 dsh 运行的请求系统提示差异\n")
    tables.append(
        f"- 系统提示长度：{mechanism['prompt_chars'][0]} / {mechanism['prompt_chars'][1]} 字符；"
        f"公共前缀 {mechanism['common_prefix_chars']} 字符后即分叉。"
    )
    tables.append(f"- 分叉处上下文：`{mechanism['divergence_context']}`")
    if ttl:
        tables.append("\n## TTL 复测（缓存建立约 35 分钟后）\n")
        for row in ttl:
            tables.append(
                f"- {row['tag']} ({row['condition']}, {row['doc']}): prompt={row['prompt_tokens']}"
                f"，命中={row['cache_hit_tokens']}，未命中={row['cache_miss_tokens']}"
            )
    (OUT / "tables.md").write_text("\n".join(tables), encoding="utf-8")

    figure(channel_b, OUT / "fig_hit.pdf")
    figure(channel_b, OUT / "fig_hit.png")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
