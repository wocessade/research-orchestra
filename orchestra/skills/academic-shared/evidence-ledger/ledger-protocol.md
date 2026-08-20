# Evidence Ledger Protocol

证据账本（Evidence Ledger）是写作阶段自动维护的结构化记录，将论文中的每个论断（claim）追溯到其引用来源。受 Paper-Pilot 的 Evidence Ledger 模式启发。

## 核心原则

1. **每段一记录** — 写作 agent 每写完一个包含论断的段落，追加一条 ledger 条目
2. **可追溯** — 每个条目记录 `claim_text`、`source_ref`、`source_excerpt`（原文摘录）
3. **可审计** — evaluate 阶段独立审计 ledger，标记孤儿论断和出处不匹配

## Ledger 条目格式

每一条 ledger 条目是一个 JSON 对象，追加写入 `{output_dir}/evidence_ledger.jsonl`（每行一条）：

```json
{
  "claim_id": "CLM-001",
  "section": "2.3",
  "subsection": "2.3.1",
  "paragraph_index": 4,
  "claim_text": "Prior work has shown that federated learning reduces communication costs by up to 40% in cross-device settings.",
  "source_ref": "[McMahan et al., 2017]",
  "source_excerpt": "We find that the FedAvg algorithm reduces communication rounds by 10-100x compared to synchronous SGD in heterogeneous networks.",
  "confidence": "high",
  "claim_type": "factual",
  "audit_status": "pending"
}
```

### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `claim_id` | 唯一标识，格式 `CLM-{NNN}` | CLM-001 |
| `section` | 所属章节 | 2.3 |
| `subsection` | 所属子节（可选） | 2.3.1 |
| `paragraph_index` | 段落在章节中的序号（0-based） | 4 |
| `claim_text` | 论断原文（完整句） | Prior work has shown... |
| `source_ref` | 引用标记（文内引用格式） | [McMahan et al., 2017] |
| `source_excerpt` | 来源原文摘录（支撑该论断的句子） | We find that... |
| `confidence` | 论断可信度：`high`/`medium`/`low` | high |
| `contribution_id` | Optional link to confirmed contribution (`C1`…) / experiment map | C1 |
| `claim_type` | 论断类型：`factual`/`attribution`/`method`/`result`/`interpretation` | factual |
| `audit_status` | 审计状态：`pending`/`verified`/`orphan`/`mismatch` | pending |

## 写作 agent 集成

写作 agent 在每个章节写作完成后，执行以下步骤：

1. 扫描刚写的段落，识别每个包含引用标记 `[...]` 的论断句
2. 为每个论断创建一条 ledger 条目：
   - `claim_text`: 包含引用的完整句子
   - `source_ref`: 该句的引用标记
   - `source_excerpt`: 从参考文献中摘录的对应原文（如文献不可达则为 `null`）
   - `confidence`: 根据是否直接访问了原文来判断（有原文摘录=high，仅凭记忆=low）
3. 追加到 `evidence_ledger.jsonl`

### 写入位置

- 文件: `{output_dir}/evidence_ledger.jsonl`
- 格式: JSONL（每行一个完整 JSON 对象，无外层数组）
- 编码: UTF-8
- 追加模式: 每条新条目 append 到文件末尾，不覆盖已有条目

## 审计规则

evaluate 阶段新增 `evidence_ledger_auditor` agent，执行以下检查：

### 1. 孤儿论断检测
扫描 ledger 中 `confidence=low` 的条目。`confidence=low` 意味着写作 agent 无法提供 source_excerpt（可能凭记忆生成）。标记为审计关注。

### 2. 出处不匹配检测
对 `confidence=high` 的条目，验证 `claim_text` 的核心主张与 `source_excerpt` 是否一致。如 `source_excerpt` 内容不支持 `claim_text` 中的论断，标记为 `mismatch`。

### 3. 证据密度评分
按章节统计：总论断数 / 总段落数。阈值：
- ≥ 0.8: 高证据密度（good）
- 0.4-0.8: 中等（acceptable）
- < 0.4: 低证据密度（需补充引用）

### 4. 审计报告输出

```json
{
  "audit_id": "AUDIT-EV-001",
  "total_claims": 42,
  "status": {
    "verified": 35,
    "orphan": 4,
    "mismatch": 2,
    "pending": 1
  },
  "orphan_claims": ["CLM-012", "CLM-023", "CLM-031", "CLM-040"],
  "mismatched_claims": [
    {"claim_id": "CLM-005", "issue": "claim_text overstates source_excerpt scope"}
  ],
  "density": {
    "overall": 0.67,
    "by_section": {"1": 0.5, "2": 0.8, "3": 0.6}
  },
  "recommendation": "Review orphan claims CLM-012, CLM-023, CLM-031, CLM-040. Source not found for these claims."
}
```

## 集成到 Stage

### 写作阶段（S4/T4/C3）
- 写作 agent prompt 末尾增加："在完成每个章节后，按 evidence-ledger 协议生成 ledger 条目"
- ledger 文件路径为 `{output_dir}/evidence_ledger.jsonl`

### 评审阶段（S7/T5/C4）
- evaluate 配置增加 `evidence_ledger_auditor` agent
- 审计结果纳入综合评分
- 孤儿论断数 > 5 且占比 > 20% → 标记为 AI 幻觉风险，建议人工核查

### 命令（/check-refs）
- 独立命令，读取 `evidence_ledger.jsonl` 并运行审计
- 不修改论文，只输出审计报告
