# /check-refs — 引用身份与论断支撑检查

在 S2/T2 检索后或 S7/T5 评审时使用。书目身份核验、账本链接检查、原文支撑核验分别报告。

## 执行

以 `{skills_root}` 为学术技能组目录：

```bash
python {skills_root}/academic-shared/literature/verify_citations.py --input {output_dir}/bibliography.json --output-dir {output_dir}/verification
python {skills_root}/academic-shared/literature/verify_citations.py --validate-ledger {output_dir}/evidence_ledger.jsonl --verification-report {output_dir}/verification/verification_report.json --output-dir {output_dir}/verification
```

只有 .bib 时，先使用 `academic-shared/literature/bib_to_bibliography.py refs.bib -o bibliography.json`。
第一条命令检查书目信息；第二条只检查账本与书目记录的链接，不能证明原文支撑。内部实验/推导产物单列，空引用与未知 key 不得静默视为通过。没有书目报告时仍执行下述正文证据审计，不为运行命令伪造报告。

随后按 [账本协议](../evidence-ledger/ledger-protocol.md) 从当前正文提取需证据论断，包括无引用强论断；核对当前修订、原文/产物、定位、数值、方向和范围。核心及变更论断全部检查，其余按影响抽查。
按 [引用库规则](../citation/citation-support-bank.md) 分别写 verified（仅书目身份）及 support_status。来源不可获取是未核验，API 未匹配不等于虚构；已读来源不支持才记 mismatch。

## 输出

- verification/verification_report.json：书目身份核验。
- verification/ledger_validation.json：最新账本记录的链接覆盖情况，support_check=not_performed；不得当成语义审计通过。
- evidence_audit.md：当前稿件的原文/产物支持审计及未核验范围；具体缺口进入本轮累计问题清单。

报告分别列书目已匹配、无法匹配、内部证据关联、支持/部分支持/不匹配/未核验数量。不按引用密度打分，不向正文追加工具验证免责声明。
