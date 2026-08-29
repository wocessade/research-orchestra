# Bogda Stage D 验收：Owner Console

日期：2026-08-29  
工作树：`D:\pythonProject\.worktrees\bogda-stage-d-console`  
分支：`codex/bogda-stage-d-console`  
范围：3101 mock-all 影子控制台。**不是 Gate 6 通过，不是真 Prefect 写入，不是 3100 切换。**

## 结论

Stage D 的 owner 操作面在 mock 剖面下可验收：决策跑道、运行预算审计、模型策略、受控运行准备。宿舍机硬件、真实 usage/dsh、Gate 6 维护窗仍按延期登记册挂起。

## 浏览器矩阵

在 Playwright 视口 `desktop-1440`、`1280`、`768`、`390`、`360`、`320` 上覆盖：

- 决策 hash 定位、多动作选择、冲突后必须重确认、不可逆勾选。
- 运行预算 `ready` 与 `usage-unknown`（固定文案：人工核对、禁止盲重试）及唯一决策链接。
- 模型策略不可变安全基线、项目覆盖后恢复继承、冲突后重新确认。
- 受控准备：`生成服务端预览` → `确认并提交运行`；键盘焦点 trap；Escape 还原。
- `real-readonly` 能力下策略保存与 Deployment 提交按钮保持禁用。
- axe serious/critical 空；reduced-motion；无横向溢出。

## 视觉 QA

检查了决策跑道、运行详情预算、模型策略、准备对话框在桌面与 320/360px。保留既有 conifer/lake 壳层与字体。

**去掉的多余视觉元素：** 运行预算状态条里与「恢复条件」列表重复的同一段恢复文案。状态条只保留状态名，恢复说明只出现在下方单一 callout。

**窄屏修补：** 主导航第六项「模型策略」使原 5 列底栏会挤出视口；改为 3×2，并让策略字段在 840px 以下单列。

## 明确未关闭

宿舍机、Wake Bridge、真实 Prefect S1/S2、Gate 6 受控重启/restore、3100 切换。见延期登记册 DEF-01–15 与 NOW-03/NOW-04。
