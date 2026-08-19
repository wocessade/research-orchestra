# Subsystem-3 Codex 双 agent 验收报告（历史代码独立审）

- 日期：2026-08-19
- Mission：027_subsystem-3-codex-dual-agent
- 协议：计划文档《Subsystem 3: 双 agent 验证（CC × Codex）Implementation Plan》§C
- 目标代码：`orchestra/broker/executor.py`（mission 021-025 已验收在役，89 行）

## 一、互审真实调用

- 命令：`codex_modes.py mutual-review ../broker/executor.py --context review-context.txt --timeout 1800 --out codex-review-executor.json`
- 结果：status=ok，findings=3（severity 全 med），artifact 存档 `orchestra/reports/artifacts/codex-review-executor.json`
- 调用史：第 1 次 600s 超时（本机 codex 冷启动 ~128s + 仓库探索耗时；超时产物存档 `D:\Temp\subsystem-3\codex-review-executor-timeout.json`）；第 2 次被 agent 轮询误杀（非 codex 错误）；第 3 次 context 增加「只用提供内容、不动工具」+ --timeout 1800 成功——抑制仓库探索是本机跑通互审的关键
- codex 原始 findings 全文见 artifact `raw` 字段（3 条，逐字引用）

## 二、CC 逐条判定表

| # | sev | codex 引位置（实际位置） | codex 主张 | CC 判定 | 依据（源码独立复现） |
|---|---|---|---|---|---|
| 1 | med | line 25（实际 29） | result_dir 直接拼进 results_root，绝对路径/`..` 可让 attempt 输出逃逸 results 树 | **真问题**（新发现，安全加固） | `taskfile.py:48` `result=fields["result"]` 原样透传；`executor.py:29` 直接 `Path(results_root) / spec.result_dir`。逃逸后 attempt 目录与 dsh 沙箱 cwd 均落 results_root 外。任务文件由编排者自写（信任域内），但误写 `result:` 值即越界写入，属 defense-in-depth 缺口 |
| 2 | med | line 31（准确） | attempt 目录分配非原子（TOCTOU），并发同 result_dir 可撞号覆写 | **真问题**（潜在，当前不可触发） | `executor.py:31-34` exists 检查 + `mkdir(exist_ok=True)` 存在竞态窗口；当前 dispatcher 单任务串行执行不可触发，属并发加固项，修复成本 ~2 行 |
| 3 | med | line 66（实际 69-70） | Windows 超时只杀直接子进程，孙进程留孤儿 | **真问题**（新发现，已获类证实锤） | Windows 分支 `proc.kill()` 只杀 cmd.exe；今日 Task 2 开发中实测同型 bug（.cmd shim → node 孙进程持管道挂死）。Pi(Linux) 已由 killpg 修复（哨兵 CONCERN-5 遗留），Windows 开发路径裸奔 |

- 误报 0 条；风格建议 0 条（context 引导「风格少给」生效，口径见 §六）

## 三、命中率

**命中率 = 3/3 = 100%**（真问题 3 / 清单总数 3；artifact：`orchestra/reports/artifacts/codex-review-executor.json`）

- 对照已知缺陷档案（cwd / attempt / 超时 三区域）：档案内缺陷均已修复，codex 找到的 3 条是**同区域的更深层新问题**——与档案区域吻合但无一重复，说明 codex 不是复述已知项
- 新问题记录：3 条全部为新（#1 路径逃逸、#3 Windows 树杀缺口为全新；#2 竞态为潜在）

## 四、通信方式②③能力存在性验证（仅验证，不脚本化）

- `codex exec resume`：**存在**——按会话 UUID 或 thread name 续接；`--last` 取最近会话；`--all` 关闭 cwd 过滤
- `codex exec fork`：**存在**——按 UUID/thread name fork 出新会话，可带续接 prompt
- 意外发现：`codex exec review` 内置仓库审查子命令；另有 `--ephemeral`（会话不落盘）、`-o/--output-last-message FILE`（末条消息直接写文件，可替代 JSONL 解析）、`--output-schema FILE`（JSON Schema 硬约束最终回复——比 prompt 契约更强的输出约束，v2 候选）
- 证据：`D:\Temp\subsystem-3\codex-help.txt`（三条 help 均 exit 0）

## 五、零回归证据

- broker：`python -m unittest discover -s tests` → **Ran 41 tests OK**（orchestra/broker/tests/，2026-08-19 实测）
- scripts：discover 全量 → **Ran 124 tests OK**（76 既有 + 48 新，Task 3 记录）
- usage-monitor 58+1 / 墨水屏面板 / 雷达：本 mission 零改动（commit 范围仅 scripts 两新文件 + 本报告）

## 六、判定口径与局限

- 行号精度：codex 引用的行号存在 ±4 行偏差（#1 引 25 实 29、#3 引 66 实 69-70、#2 准确）——判定按主张内容对照源码复核，不以引号为准；file 字段为空（上下文隐含目标文件）
- 风格类不计入命中率分母：本清单 0 风格条，分母=3
- v1 已知局限：codex_modes 结果未携带 elapsed_s 与 token usage（事件流 turn.completed.usage 未被 modes 层转发）——费用核算改进列入 v2 候选
- executor.py 3 条 finding 本 mission 不修（Broker 零改动约束；修复需 Pi 部署窗口），列入后续 broker 迭代候选：path 校验 1 行、原子 mkdir 2 行、Windows taskkill /T 沿用 codex_exec.py 既有模式

## Reviewed

- Reviewed by CC（opus）：判定表 3/3 经源码独立复现（taskfile.py:48、executor.py:29/31-34/69-70），命中率口径见 §三
- Reviewed by 哨兵：2026-08-19 终审通过（AC 1-8 全成立；2 LOW + 1 cosmetic 已处置，处置记录见 mission AUDIT.md）
- 状态：ok
