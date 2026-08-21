# GPT-SOL 对 Research Orchestra 的锐评

评审基线：`main`，提交 `39d284a`  
评审方式：只读检查仓库中的 Broker、脚本、配置、模板、Skill 快照、测试和验收报告。

## 总体判断

Research Orchestra 已经不是玩具，但还没有达到“可信基础设施”的标准。它最强的是 Broker 核心工程化，最弱的是系统治理：门禁、文档、配置和 Skill 数量快速增长，却没有形成足够清晰的单一事实源。

综合评分：**7/10**

| 维度 | 评分 | 评价 |
|---|---:|---|
| Broker 核心 | 8.5 | 状态机、重试、依赖传播和路径安全较扎实 |
| 雷达流水线 | 8 | 阶段化和确定性校验明显优于纯 Prompt 编排 |
| 质量门禁 | 7 | 有真实门禁，但关键传递依赖仍可能静默降级 |
| Skill 体系 | 5.5 | 资产很多，真正接线较少，复制和漂移成本偏高 |
| 部署运维 | 6 | 有迁移预检，但发布过程还不是原子事务 |
| 验收可信度 | 5.5 | 报告丰富，但部分证据无法从仓库重放 |
| 文档治理 | 5 | 状态信息分散，文档开始反噬维护效率 |

## 做对的部分

### Broker 是真实运行内核

`orchestra/broker/db.py`、`dispatcher.py` 和 `executor.py` 已经形成完整的异常处理路径：

- 原子 claim 和 attempt 目录分配；
- 超时与进程树终止；
- 失败重试和崩溃恢复；
- 缺失依赖、依赖环和上游失败传播；
- `blocked`、`invalid` 等明确终态；
- artifact 校验失败不会因为进程退出码为 0 而误报成功。

很多 Agent 项目只有 Prompt 和流程图，这里已经有一个能够处理异常路径的任务内核。这是整个项目最值得保留的资产。

### 雷达阶段化方向正确

`fetch → rank → render → notify` 的职责划分合理：

- LLM 负责需要判断的评分；
- Python 负责确定性排序和语义校验；
- 上游 SHA-256、论文 ID 和原始字段形成闭环；
- 通知区分 `sent`、`not_sent` 和 `unknown`；
- 发送结果不明确时拒绝盲目重发；
- 上游失败会明确阻断下游。

这是真正落地的“松生成、严验证”，不再让 LLM 同时扮演研究员、排序器、校验器和邮件客户端。

### 历史事故被吸收到代码

PID 复用、symlink 逃逸、attempt 竞态、旧任务迁移、Windows 进程树和通知模糊结果等问题，都已经转化为实现和测试，而不是停留在“注意事项”中。

这说明系统经历过真实运行反馈，不是一次性演示项目。

## 主要问题

### P0：Skill 门禁没有覆盖真实依赖边界

`orchestra/config/skills.json` 锁定了 `academic-research-engine` 的入口和部分契约文件，但 `ingest_run.py` 实际还依赖：

```text
academic-shared/research/metrics.schema.json
```

这个传递依赖没有进入当前 digest。更危险的是，`ingest_run.py` 对 `jsonschema` 和 schema 文件采用可选逻辑：

```python
if jsonschema is not None and SCHEMA_PATH.is_file():
    jsonschema.validate(...)
```

因此可能出现：

- schema 内容变化但 Skill digest 不漂移；
- schema 文件缺失但 ingest 继续；
- `jsonschema` 未安装但 ingest 继续；
- 表面上摘要门禁通过，实际上只执行浅层字段检查。

这会制造错误安全感。修复方向应当是：

- 将 schema 纳入传递依赖摘要；
- schema 缺失时直接失败；
- `jsonschema` 缺失时直接失败；
- manifest 区分入口、直接依赖和传递依赖。

### P0：验收证据无法完全重放

部分验收报告引用：

- `D:\Temp\...`；
- Pi 本地日志；
- 未入库的 results；
- 仓库外截图和 JSON。

仓库中还存在同一任务、同一 attempt 的冲突状态：

```text
orchestra/results/T-.../attempt-2/state.json          done
orchestra/results/results/T-.../attempt-2/state.json  failed
```

人可以结合历史解释，机器无法判断哪一份才是真相。因此目前的 `reviewed: ok` 更接近人工签字，不是可重复验证的证据包。

验收结果应保存为只追加、带输入摘要、代码提交号和 artifact hash 的 evidence bundle。报告只能引用仓库内或持久存储中可校验的证据。

### P1：部分配置只是装饰性控制面

`orchestra/config/rules.yaml` 和 `model-routing.json` 看起来像系统控制中心，但运行代码没有完整消费它们：

- `default_executor` 没有接入任务解析；
- `degradation_order` 没有自动执行逻辑；
- 模型路由表没有统一 resolver；
- 任意 `model` 字符串可以进入任务卡；
- 修改配置后，系统行为未必改变。

配置存在却不生效，比没有配置更危险。操作者会误以为运行策略已经改变。

原则应当非常简单：配置存在，就必须有消费代码和回归测试；否则删除，或明确标记为纯文档。

### P1：Task Schema 仍然半开放

任务卡是整个系统的核心接口，但当前解析器仍然可能：

- 接受未知字段；
- 用后值覆盖重复 key；
- 不限制 `timeout` 的合理范围；
- 不验证 `model`；
- 静默忽略拼错的 `required_outputs`；
- 对未声明产物契约的任务继续采用 `exit 0 = done`。

危险的不是非法任务失败，而是错误配置被当作合法任务运行。

应当拒绝未知字段和重复 key，并校验 timeout、executor、model、产物契约之间的组合关系。

### P1：部署不是原子发布

`deploy_broker.sh` 已经具备迁移预检和停服保护，但发布过程仍然是逐个覆盖文件、移动 unit、原地修改配置，然后重启服务。

如果中途失败，远端可能形成新旧文件混合版本。当前恢复策略倾向于重新启动部分覆盖后的 Broker，而不是回到已知良好版本。

更可靠的部署模型应当是：

```text
releases/<git-sha>/
    完整上传
    hash 校验
    smoke test

current -> releases/<git-sha>   # 原子切换
```

失败时将 `current` 切回上一版本。Reporter 还应暴露运行中的 git SHA 和配置摘要，使控制台能够判断“仓库已修”和“远端已部署”是否一致。

### P2：Skill 资产规模超过实际集成规模

`orchestra/skills/` 已有数百个文件，但真正被 Orchestra 强接线的 Skill 很少。当前存在多层复制：

```text
academic-shared canonical
→ journal/thesis/coursework 副本
→ 仓库 Skill 快照
→ ~/.claude/skills 活副本
```

这使系统难以回答：

- 哪份文件是唯一源头；
- 差异是有意分叉还是漏同步；
- 哪些 Skill 真正在生产路径运行；
- 哪些只是参考资料；
- 哪些变化必须触发系统回归。

建议将 Skill 明确划分为：

- `runtime-integrated`
- `distribution-only`
- `reference-only`
- `deprecated`

只有 `runtime-integrated` 进入强 digest、测试和发布门禁。

### P2：文档开始成为第二套状态数据库

README、CLAUDE 和验收报告中已经出现：

- digest 是否锁定的描述互相冲突；
- 测试数量不一致；
- 已完成事项仍标记为进行中；
- sync 行为与文档不一致；
- 同一状态复制到多个文件。

测试数量、commit SHA、Skill digest、部署版本和验收状态不应手工写入多个 Markdown。它们应由一个命令生成，文档只解释含义，不保存易过期的运行状态。

## 真实门禁与人工纪律

### 已真实接线

- Task 必填字段、部分枚举和路径逃逸检查；
- 依赖缺失、依赖环和上游失败传播；
- attempt 原子目录；
- 已声明的 required、JSON、validation 和领域 validator；
- 进程非零退出和超时；
- 必需 Skill digest 状态；
- ingest 前 `exp_id` 与 card ID 一致；
- 雷达阶段 artifact validator；
- 部署前旧单体任务迁移检查；
- notify 的 at-most-once 状态。

### 仍主要依赖人工

- `rules.yaml` 的默认执行器和降级顺序；
- `model-routing.json` 的自动模型决策；
- CC 写入 reports 的复查 gate；
- “所有数字必须来自 artifact”的全局约束；
- 未声明 `required_outputs` 的通用任务质量；
- `jsonschema` 和共享 metrics schema 的必备性；
- 全部 Skill 快照的版本一致性；
- 远端运行版本与仓库 git SHA 一致性；
- 验收报告引用证据的可用性；
- 文档中的测试数字和状态更新。

## 最高杠杆改进

### 建立唯一验收入口

增加统一命令，例如：

```bash
python scripts/orchestra_check.py
```

该命令生成机器可读报告，覆盖：

- 全部测试；
- shell 语法；
- Task Schema；
- Skill 传递依赖 digest；
- 配置是否被代码消费；
- Prompt 回归；
- 报告证据是否存在；
- ignored 目录中是否仍有 tracked 文件；
- 当前 git SHA；
- 远端部署 SHA；
- 部署 smoke 状态。

CI、部署和验收报告都只认这份结果。README 不再手写测试数量。

### 收紧契约来源

集中处理以下问题：

- Task header 拒绝未知字段和重复 key；
- 限制 timeout；
- model 只能来自路由表；
- `rules.yaml` 要么接线，要么删除；
- metrics schema 和 `jsonschema` fail-closed；
- Skill digest 覆盖传递依赖；
- 通用任务默认要求最小产物契约。

目标是让“配置存在”“摘要已锁”“任务格式严格”都成为代码事实，而不是操作者约定。

### 原子部署与证据去歧义

- 使用 `releases/<sha>` 部署；
- 原子切换 `current`；
- 自动 smoke 和回滚；
- Reporter 上报运行 SHA；
- 验收结果保存为只追加 evidence bundle；
- 清理冲突的历史 results；
- 报告只引用带 hash 的持久 artifact；
- 对确需复制的 Skill 文件生成 manifest，并在 CI 检查 drift。

## 结论

Research Orchestra 的问题已经从“能力不足”转变为“能力增长速度超过治理能力”。

Broker 内核值得继续建设，但下一阶段不适合继续增加 Agent、Skill、Prompt 或控制台功能。优先补齐单一事实源、传递依赖门禁、原子部署和可重放验收，现有架构才能从“工程上多数可用”提升到“长期可证明地可靠”。
