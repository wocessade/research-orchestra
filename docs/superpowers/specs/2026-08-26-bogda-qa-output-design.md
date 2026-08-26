# Bogda 并行问答产物合约

> 日期：2026-08-26
>
> 状态：待 owner 批准（未实施）
>
> 来源：桌面《bogda通用任务接口设计决策.md》两轮评审后的收窄方案（线 A）

## 1. 定位

本切片只解决 2026-08-26 入学考试暴露的**模型产物**问题：输出格式不统一、依据/置信度无法程序化、多份答案无法机械合并、过期产物被误采信。

它是纯库：Pydantic 合约 + 解析 + 合并 + 落盘。不是任务类型系统，不是调度器，不迁 `research_cycle`，不接 Prefect，不改 3101/3100，不改 Pi。

exam-watch 的凭据/心跳/控制台问题（讨论稿教训 6–8）是 **线 B**，另开 spec，不在本文件范围。

## 2. 已锁定决策

| 主题 | 决策 |
|---|---|
| 范围 | 只做并行问答的产物层；`Coordinator.run` / `research_cycle` 不动 |
| 强制方式 | 工具名 `submit_answers` + `QAOutput.model_validate`，fail-closed |
| 题型 | 按题声明 `single` / `multi` / `judge`，禁止整卷一个 `qa_format` |
| 依据与置信度 | `evidence`、`confidence` 必填；空字符串非法 |
| 一致规则 | 仅当所有 runner 对同一题规范化后的 `answer` 相同才采信；任何分歧进 `pending`，不做多数决 |
| 变更 | 产物带 `revision`；合并时指定期望 revision，过期即抛错。不实现在途补丁广播 |
| 任务卡 | v1 不解析 Markdown/YAML 卡；CC 直接构造/读 JSON |
| 别名表 | `runner` 为自由字符串；不新建 model-routing |
| 预算 | 本切片不暴露 AgentBudget；既有四墙不变 |
| 与 T-*.md | 分家。不新增 `bogda/tasks/` 方言 |
| 插件 | 不建 `TYPE_REGISTRY`、不把 Coordinator 改成类型解释器 |
| 运维字段 | 不在本合约放 `env` / `alerts` / `artifacts` 通道声明 |

## 3. 合约

工具名常量：`submit_answers`。

模型回复形状（`tool` 仅用于解析入口，不进入 `QAOutput`）：

```json
{
  "tool": "submit_answers",
  "task_id": "T-20260826-001",
  "revision": 1,
  "runner": "h1",
  "answers": [
    {
      "qno": 1,
      "format": "single",
      "answer": "A",
      "evidence": "手册第3章",
      "confidence": "high"
    }
  ]
}
```

### 3.1 字段

| 模型 | 字段 | 约束 |
|---|---|---|
| `QAAnswer` | `qno` | int ≥ 1 |
| | `format` | `single` \| `multi` \| `judge` |
| | `answer` | 解析时规范化，见 §3.2 |
| | `evidence` | 非空字符串 |
| | `confidence` | `high` \| `medium` \| `low` |
| `QAOutput` | `task_id` | 非空字符串 |
| | `revision` | int ≥ 1 |
| | `runner` | 非空字符串，合并时用作文件名与归因 |
| | `answers` | 非空；`qno` 不重复 |
| `QAConsensus` | `qno`, `format`, `answer` | 采信值 |
| | `evidence` | 各 runner 依据，去重保序 |
| | `confidence` | 同意各方中**最低**档 |
| `QADivergence` | `qno`, `format` | |
| | `by_runner` | 该题各方 `QAAnswer`（含 runner 在所属 `QAOutput`） |
| `QAMergeResult` | `task_id`, `revision` | 与期望值相同 |
| | `agreed` | `tuple[QAConsensus, ...]` 按 qno 升序 |
| | `pending` | `tuple[QADivergence, ...]` 按 qno 升序 |

`QADivergence.by_runner` 的每条必须能追溯 runner。实现上用带 `runner` 字段的答案视图：

```python
class QARunnerAnswer(QAAnswer):
    runner: str
```

### 3.2 答案规范化（解析时执行，合并只比较规范化后的值）

| format | 规则 | 合法结果示例 |
|---|---|---|
| `single` | strip + 大写，必须是恰好一个 `A`–`D` | `A` |
| `multi` | 取出全部 `A`–`D`，去重排序后拼接；至少一字母 | `AB`（输入 `b,a` / `BA` / `A B` 皆可） |
| `judge` | `对`/`正确`/`true`/`T`/`yes` → `对`；`错`/`错误`/`false`/`F`/`no` → `错`（大小写不敏感） | `对` / `错` |

无法规范化 → `pydantic.ValidationError`。

### 3.3 解析

`parse_qa_reply(reply: Mapping) -> QAOutput`

- `reply["tool"] != "submit_answers"` → 抛现有 `UnknownTool`（与 Coordinator 同一异常类型）
- 其余字段 `QAOutput.model_validate`；失败即 `ValidationError`
- 不猜测缺字段、不从 prompt 口述补全

### 3.4 合并

`merge_qa_outputs(outputs, *, task_id: str, revision: int) -> QAMergeResult`

Fail-closed：

| 条件 | 异常 |
|---|---|
| `outputs` 为空 | `ValueError` |
| 任一 `task_id` 不符 | `TaskIdMismatch` |
| 任一 `revision` 不符 | `StaleRevision` |
| `runner` 重复 | `ValueError` |
| 各方 `qno` 集合不一致 | `IncompleteAnswers` |
| 同一 `qno` 的 `format` 不一致 | `FormatConflict` |

比较：同一 `qno` 上各方规范化 `answer` 全相同 → 进入 `agreed`；否则进入 `pending`。不看 evidence 是否相同。

### 3.5 落盘

根目录由调用方传入（测试用 tmp；实战可用 `D:\Temp\...`，不入库）。

```
<root>/
  answers/<runner>.json    # QAOutput
  merge.json               # QAMergeResult
```

- `write_runner_answers(root, output) -> Path`
- `write_merge_result(root, merged) -> Path`
- JSON：UTF-8，`model_dump_json(indent=2)` + 尾换行
- 不写 `verdict_pending.json` / `merged.json` 两个互斥文件；`pending` 是否为空由 `merge.json` 字段表达

## 4. 模块落点

| 路径 | 职责 |
|---|---|
| `bogda/src/bogda/agents/qa.py` | 全部合约、规范化、解析、合并、落盘 |
| `bogda/tests/agents/test_qa.py` | 本切片全部单测 |
| `bogda/src/bogda/agents/__init__.py` | 导出公开名 |

**不修改：** `coordinator.py`、`contracts.py`、`flows/`、`orchestra/`、控制台、Pi 部署。既有 `tests/agents/test_coordinator.py` 必须仍通过。

## 5. 验收

在 `bogda/` 下：

```
uv run --python 3.11 pytest tests/agents/test_qa.py tests/agents/test_coordinator.py -v
```

全部通过，且无 integration / Prefect 依赖。

## 6. 明确不做

- 类型注册表、类型解释器、`research-cycle@v1` 平移
- Markdown 任务卡 / YAML front-matter / 补丁广播
- 多数决、人工裁决器、RAG、PDF 读取
- CLI、Prefect Flow、3100/3101
- `env` / `alerts` / systemd / SMTP / cookie
- 改 exam-watch / `feed_exam.py` / `feed_serve.py`

## 7. 线 B（不在本切片）

exam-watch 三次故障（EnvironmentFile 格式、console 不读权威文件、心跳语义）另开 `docs/superpowers/specs/` 文档，由 deploy 校验与 console 契约修复，不并入 `qa.py`。
