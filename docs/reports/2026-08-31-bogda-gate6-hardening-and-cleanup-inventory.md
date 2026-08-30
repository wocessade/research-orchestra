# Bogda Gate 6 前全面审查与磁盘清理候选

日期：2026-08-31
范围：Bogda core、3101 Console、Pi Gate 6 只读运行证据、C/D 盘只读盘点。

## 当前结论

Bogda 的软件基线健康，尚不能宣告 Gate 6 完成：当前 trial `20260830T154019Z` 要到北京时间 2026-08-31 23:40 左右才满 24 小时。04:12 的只读抽查有 52 个样本、零缺口、零 API/数据库/OOM 失败，API 延迟 p95 为 84.62 ms，关键服务和定时器均为 active。

本轮选择修复有可复现证据、且不会扩大系统复杂度的边界：

- Pi server/worker 随 `mnt-nas.mount` 停止，并在同一挂载单元返回后重新拉起；bundle validator 固化此契约。
- Gate 6 JSONL 每条记录显式 flush + fsync；损坏记录报告准确行号。
- `bogda.ops` 改为惰性公开符号，模块入口不再产生重复导入告警。
- Console 总览保留局部来源失败，并明确区分“来源不可用”和“权威来源确实为空”。
- 导航回归测试覆盖实际六个一级入口。

必要但不适合仓促实现的事项已进入[延期工作登记册](2026-08-29-bogda-deferred-work-register.md) DEF-05、DEF-20 至 DEF-23；其中包括付费调用跨进程恢复、资源级能力、复杂 schema/分页/类型安全客户端、版本化共享契约和若干原子持久化边界。

## 验证证据

- Bogda：`646 passed, 11 skipped`。
- Console 后端：`171 passed`。
- Console 前端：`116 passed`。
- OpenAPI 契约检查、TypeScript 与 Vite production build：通过。
- Playwright 六视口矩阵：`127 passed, 5 skipped`，覆盖无障碍、键盘、降级、端口安全和 320 px 回流。
- 真实付费模型调用：0；生产写操作：0；Gate 6 仅做只读探测。

## 磁盘盘点原则

以下全部是候选，不是删除授权。本轮未删除、移动或清空任何文件。个人文档只给汇总，不列文件名；Codex/Claude 目录不建议整目录删除，需二次细分到可再生 cache/log 后再处理。

### C 盘可再生候选

| 候选 | 当前大小 | 建议动作 | 风险/说明 |
|---|---:|---|---|
| `%LOCALAPPDATA%\Temp` | 3.08 GB | 关闭应用后清理可删除项，锁定项跳过 | 大部分近期文件；不能按年龄一刀切 |
| `C:\Users\19041\.cache` | 2.14 GB | 先按子目录列出，再删明确可再生缓存 | 约 111 MB 超过 180 天 |
| `%LOCALAPPDATA%\npm-cache` | 2.04 GB | 可用 npm 官方 cache 清理方式 | 后续安装会重新下载 |
| `%LOCALAPPDATA%\uv\cache` | 1.71 GB | 可用 uv 官方 cache 清理方式 | 后续环境会重新下载/构建 |
| `%LOCALAPPDATA%\pip\Cache` | 0.36 GB | 可用 pip 官方 cache 清理方式 | 后续安装会重新下载 |
| `%LOCALAPPDATA%\CrashDumps` | 0.07 GB | 若不再排查崩溃可删除 | 会失去旧崩溃转储 |
| `C:\Windows\Temp` | 0.05 GB | 仅清理系统允许删除的项 | 需要跳过占用或拒绝访问项 |

### C 盘需要二次细分，不可整目录删除

| 目录 | 当前大小 | 处理意见 |
|---|---:|---|
| `C:\Users\19041\.codex` | 1.74 GB | 含任务、会话、插件与缓存；只列出 cache/log 子目录后再批准 |
| `C:\Users\19041\.claude` | 0.70 GB | 含配置/历史与缓存；不可整目录删除 |
| `C:\Users\19041\.agents` | 0.10 GB | 主要是当前技能资产，不建议清理 |
| `%LOCALAPPDATA%\OpenAI\Codex` | 0.75 GB | 当前应用数据且较新，不建议整目录清理 |

个人资料汇总：Desktop 约 0.31 GB，其中超过一年约 29 MB；Documents 约 1.99 GB，其中超过一年约 72 MB。没有发现超过 100 MB 且超过一年的单个文件。这些不属于垃圾，不建议自动删除。

### D 盘工作树候选

下列旧工作树均为 clean，且 HEAD 已在 `origin/main` 祖先链中；合计约 1.89 GB。获批后应使用 `git worktree remove`，不能直接递归删除目录。

| 工作树 | 大小 |
|---|---:|
| `paid-model-runtime` | 0.29 GB |
| `policy-panel-redesign` | 0.25 GB |
| `stage-d-console` | 0.45 GB |
| `stage-e-integration` | 0.65 GB |
| `stage-e-owner-control` | 0.25 GB |

当前 `bogda-gate6-hardening` 工作树约 0.44 GB，任务完成前保留。另有空目录 `bogda-console-local-launcher`，大小为 0，可在批准后顺手移除。

## 建议的后续清理批次

1. 低风险：npm、uv、pip cache，CrashDumps，旧 clean worktrees（预计约 6.1 GB）。
2. 中风险：用户 Temp 与 Windows Temp，只删系统允许项并记录跳过列表（最多约 3.1 GB）。
3. 需再次盘点：`.cache`、`.codex`、`.claude` 的子目录；不碰配置、任务状态、会话或插件资产。

任何批次都要先显示精确目标，再获得 owner 明确批准；个人资料目录不纳入自动清理。
