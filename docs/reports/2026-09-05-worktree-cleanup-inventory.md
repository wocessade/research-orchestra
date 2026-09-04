# 2026-09-05 工作树清理清单

## 结论

初次盘点时不执行删除；后续在用户明确同意后按本清单实施。Bogda 历史开发分支均已成为 `origin/main` 的祖先，工作树清理不删除这些分支。

## 执行结果

用户随后授权继续推进。`bogda-console-rk3528`、`bogda-gate6-hardening`、`bogda-paid-model-runtime`、`bogda-policy-panel-redesign`、`bogda-pre-runner-land`、`bogda-stage-d-console`、`bogda-stage-e-integration`、`bogda-stage-e-owner-control`、`local-main-salvage` 与 `bogda-gate7-real-shadow` 共十个工作树已在逐项确认干净且已合入后移除；未使用 `--force`，对应分支均保留。

四组 worktree-local `.tasks` 已在删除前逐文件校验并归档：文件数分别为 6、6、6、44。当前只保留主工作树、doc2ppt 和 RF 三个工作树。

## A：可以清理的已合入工作树

以下工作树没有已跟踪或未跟踪改动，且 HEAD 已包含在 `origin/main`。删除工作树不会删除远端 `main` 中的成果；是否随后删除本地分支应另行决定。

| 工作树 | 分支 | HEAD | 备注 |
| --- | --- | --- | --- |
| `.worktrees/bogda-console-rk3528` | `codex/bogda-console-rk3528` | `97c5c25` | RK3528 控制台部署阶段已合入 |
| `.worktrees/bogda-gate6-hardening` | `codex/bogda-gate6-hardening` | `d05ccd6` | Gate6 已合入 |
| `.worktrees/bogda-policy-panel-redesign` | `codex/bogda-policy-panel-redesign` | `a9e29d1` | 策略页重设计已合入 |
| `.worktrees/bogda-pre-runner-land` | `codex/bogda-pre-runner-land` | `100315e` | runner 前软件落地已合入 |
| `.worktrees/bogda-stage-e-integration` | `codex/bogda-stage-e-integration` | `69e46b5` | Stage E 集成已合入 |
| `.worktrees/local-main-salvage` | `wip/local-main-salvage` | `8aaa661` | salvage 成果已合入 |

## B：代码已合入，但删除前需导出 mission 记录

| 工作树 | 当前分支 | HEAD | 删除前动作 |
| --- | --- | --- | --- |
| `.worktrees/bogda-paid-model-runtime` | `codex/bogda-paid-model-runtime` | `63b8527` | 导出 `.tasks/active/048_bogda-paid-model-runtime` |
| `.worktrees/bogda-stage-d-console` | `codex/bogda-stage-d-console` | `13553ac` | 导出 `.tasks/active/049_bogda-owner-console-stage-d` |
| `.worktrees/bogda-stage-e-owner-control` | `codex/bogda-stage-e-owner-control` | `fad57e1` | 导出 `.tasks/completed/049_bogda-price-aware-owner-control` |
| `.worktrees/bogda-gate7-real-shadow` | `codex/bogda-now06-pre-research` | `eb4c812` | 其中忽略目录 `.tasks/` 保存 Gate7 与 NOW-06 的执行日志；状态已校准，但在删除工作树前应复制到不冲突的长期归档位置 |

该路径名称仍是 `bogda-gate7-real-shadow`，实际检出的分支已经是 NOW-06。这只是历史命名残留，不影响代码。

## C：必须保留

| 工作树 | 原因 |
| --- | --- |
| `.worktrees/codex-nature-doc2ppt-phase1` | 活跃分支已推进到 `ae5c593`，相对 `origin/main` 有 6 个独立提交，尚未合入 |
| 主工作树 `D:\pythonProject` | 当前生产开发入口；并含尚未提交的开学日程修正，待本轮提交 |

## D：先检查内容，再决定

| 工作树 | 原因 |
| --- | --- |
| `.worktrees/codex-rf-noise-generator-pcb` | 分支 HEAD 已合入，但存在未跟踪目录 `rf-noise-generator/`；未确认其是否为待保存成果前不得删除 |

## 建议执行顺序

1. 先清理 A 组中没有 worktree-local mission 档案的工作树；是否删除对应本地分支另作一次选择。
2. 将 B 组的四套 `.tasks` 记录复制到无编号冲突的长期归档，再清理对应工作树。
3. 保留 C 组继续开发。
4. 单独检查 D 组未跟踪目录，确认保存、纳入版本控制或放弃后再处理。

本清单不包含缓存、`D:\Temp`、C 盘旧文件或远端分支；这些属于独立清理任务。
