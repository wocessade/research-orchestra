# Evidence Ledger Protocol

账本记录所有需要证据的论断，供 S4/T4 写作与 S7/T5 评审共同使用。字段及状态以 [ledger-schema.json](ledger-schema.json) 为准。

## 收录范围

- 每个论断一条记录。包括带引用的事实、作者归因、研究结果，以及无引用的数值、因果、比较、创新性和适用范围声明。
- 实验结果可以关联内部产物，理论论断可以关联推导；没有外部引用不等于没有证据。
- 缺证据的强论断仍须入账，使用 `evidence_kind=missing`、空 `source_ref`、`source_excerpt=null`、`audit_status=orphan`。不得补造引文。
- 只有不承担论证作用、无需证据的一般背景常识可跳过；不把“首次”“SOTA”“普遍适用”等主张当作常识。

## 记录示例

以下是结构演示，不是真实实验结果，不得复制进论文当作事实。

```json
{
  "claim_id": "CLM-001",
  "contribution_id": "C1",
  "section": "3.2",
  "paragraph_index": 0,
  "claim_type": "result",
  "claim_text": "在该实验的独立测试集上，准确率为 92.3%。",
  "source_ref": "EXP-001/run-1",
  "source_excerpt": null,
  "evidence_kind": "experiment",
  "artifact_path": ".research/experiments/EXP-001/runs/run-1/metrics.json",
  "locator": "metrics.test_accuracy",
  "confidence": "high",
  "audit_status": "pending",
  "claim_revision": 1,
  "manuscript_revision": "draft-1"
}
```

## 字段与生命周期

文件为 `{output_dir}/evidence_ledger.jsonl`，UTF-8 JSONL；`paragraph_index` 统一从 0 开始。
`claim_id` 为稳定 ID（CLM-001…），`claim_revision` 随论断文字、证据或证据解释变化递增。
新记录写入稿件版本 `manuscript_revision`；一条记录可通过 `contribution_id` 关联贡献。
`evidence_kind` 为 literature / experiment / derivation / missing；文献摘录必须为原文，转述放在 `claim_text`。
`locator` 指明页码、表格、段落、指标键或推导步骤，`artifact_path` 指向实际分析产物。

追加新版本，不为同一论断反复分配新 ID。审计同一稿件版本中每个 claim_id 的最新修订；旧版本仅作历史。
原文修改、实验产物重算或来源变更后，新修订回到 pending；旧 verified 不能沿用。单纯移动段落可以保持结论，但须更新位置并核对原句。
与当前正文逐项对照：正文新增论断补录，正文已删论断不计入当前覆盖率，旧条目不得代替当前证据。

## 审计

现有事实/内容评审执行本协议，不依赖尚未配置的专用 agent。

1. 从当前正文独立提取需证据的论断，再与账本对照，不能只检查账本已有条目。
2. 检查文献身份、可定位原文/产物，以及主张与证据的指标、数值、方向、样本和范围是否一致。
3. DOI 存在、标题相近或 writer confidence=high 均不构成支撑证明。来源不可获取时保留 pending，确认没有来源时为 orphan；原文与声称不符为 mismatch。
4. verified 需要可定位的原文或产物，并由审计者实际核对支持关系。Schema 只能检查结构，不能证明语义正确。
5. 核心结论、数值、因果、比较、创新性论断逐项核对；其他论断按影响抽查并记录未核验项。不用“引用数/段落数”作为质量得分或添加引用的配额。
6. 输出 `{output_dir}/evidence_audit.md`：稿件版本、claim_id、状态、定位、问题严重度、修复/降级建议；并合并进该轮问题清单。关键证据缺失或不匹配按实际影响判为 Critical/Major，不能被平均分抵消。

## 兼容已有账本

旧记录可缺少新增的版本和证据类型字段，读取时按物理追加顺序定位旧修订，不改造历史文件。
旧 verified 若没有可定位证据，只能作为历史状态；下次消费时追加 pending 修订并重新核验。
旧 `discrepancy_found` 映射为 mismatch，`needs_review` 映射为 pending；保留原文件，新增记录只写 pending / verified / orphan / mismatch。
使用 [test_ledger_contract.py](test_ledger_contract.py) 验证示例、兼容入口和拒绝条件。
