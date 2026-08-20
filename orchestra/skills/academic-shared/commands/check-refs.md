# Command: /check-refs — 参考文献验证

**来源:** Claude-Scholar 的 `/check-refs` 命令 + 本系统的 5-step 验证管线

## 用途

运行时验证论文中的所有参考文献引用：
1. 检测伪造/幻觉引用（有 DOI 但 API 找不到）
2. 检测孤儿论断（evidence ledger 中有 claim 但无对应 verified reference）
3. 验证引用格式一致性
4. 生成已验证的引用列表

## 运行流程

```
1. 从 {output_dir}/bibliography.json 读取参考文献列表
   → 用 verify_citations.py 验证（多 API 交叉确认）
   → 输出 verification_report.json + verification_summary.txt

2. 如果 evidence_ledger.jsonl 存在：
   → 用 verify_citations.py --validate-ledger 交叉验证
   → 输出 ledger_validation.json

3. 汇总报告给用户：
   - 已验证引用数 / 总数
   - 伪造嫌疑引用列表（需用户确认）
   - 孤儿论断列表（有 claim 但引用无法验证）
   - 格式化引用输出（BibTeX + TXT）
```

## 用法

```bash
# 完整验证
python literature/verify_citations.py \
  --input {output_dir}/bibliography.json \
  --output-dir {output_dir}/verification \
  --fetch-abstracts --format-output

# 如 evidence ledger 存在，追加交叉验证
python literature/verify_citations.py \
  --validate-ledger {output_dir}/evidence_ledger.jsonl \
  --verification-report {output_dir}/verification/verification_report.json \
  --output-dir {output_dir}/verification
```

## 输出

| 文件 | 内容 |
|------|------|
| `{output_dir}/verification/verification_report.json` | 完整验证报告 |
| `{output_dir}/verification/verification_summary.txt` | 人类可读摘要 |
| `{output_dir}/verification/retrieved_abstracts.json` | 已获取摘要 |
| `{output_dir}/verification/verified_references.bib` | 已验证 BibTeX |
| `{output_dir}/verification/ledger_validation.json` | 账本验证报告 |

## 报告格式

向用户呈现时，用以下格式：

```
── 引用验证报告 ──
已验证: 32/35
伪造嫌疑: 1 ⚠️
  - [McMahan et al., 2017] — DOI 10.xxxx/xxxxx 在 3 个 API 中均未找到
孤儿论断: 3 ⚠️
  - CLM-012: "联邦学习将通信开销降低 40%"（引用 [McMahan, 2017] 但该引用未验证通过）
  - CLM-023: ...
推荐: BibTeX 文件已生成到 verified_references.bib
```

## 集成到 Stage

- S2/T2/C2 (文献检索后): 运行 `/check-refs` 验证已收集的参考文献
- S7/T5/C4 (评审阶段): 重新运行 `/check-refs` 验证最终引用列表

## LaTeX / BibTeX bridge

If the manuscript uses `.bib` (writingFormat=latex) and you do **not** yet have `bibliography.json`:

```bash
python literature/bib_to_bibliography.py {paper_dir}/refs.bib -o {output_dir}/bibliography.json
python literature/verify_citations.py --input {output_dir}/bibliography.json --output-dir {output_dir}/verification
```

One-shot:

```bash
python literature/bib_to_bibliography.py {paper_dir}/refs.bib -o {output_dir}/bibliography.json --and-verify --output-dir {output_dir}/verification
```

Then still run `academic-latex/scripts/verify_paper.py` for cite↔bib mechanical keys.
