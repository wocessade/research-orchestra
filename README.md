# Research Orchestra

科研任务调度项目，当前执行重心为 Bogda：RK3528 承载 Prefect、3101 和 NAS，Y7000 的 WSL2 承载 dorm-x86 worker。Orchestra 与旧 3100 已停用。

它可靠的是「任务能不能跑完、产物会不会假绿」。它**不是**自主科研体。锐评原文 `opus锐评.md` / `gpt-sol锐评.md` 已于 2026-08-28 移除；当时回复见 [`docs/reports/2026-08-22-critique-replies.md`](docs/reports/2026-08-22-critique-replies.md)。

**Bogda 落地完成并现网验收通过（2026-09-11）**：checkpoint 修复、store 接线、日志发布、付费审批链与 usage-unknown 恢复均已部署验收；3101 已开为精确白名单写入；**真实 dsh 已安装并真实验收**（run `3157b68c`，actual 0.02271 CNY）；**3101 接替 3100 落地（DEF-03 申报通过）**，自主策略已接线。报告：[2026-09-11 落地验收](docs/reports/2026-09-11-bogda-landing-acceptance.md)；恢复入口：[2026-09-10 工作交接](docs/reports/2026-09-10-bogda-runner-handoff.md)。

运行手册：[`orchestra/README.md`](orchestra/README.md)。总 spec：[`docs/superpowers/specs/2026-08-18-research-orchestra-design.md`](docs/superpowers/specs/2026-08-18-research-orchestra-design.md)。教训库：[`docs/lessons-learned.md`](docs/lessons-learned.md)。不要把手写测试数、digest、部署 SHA 抄进本文档。

仓库：GitHub private `wocessade/research-orchestra`。

---

## 现在怎么跑（2026-09-10）

```text
管理机 100.103.79.3 ──SSH── Y7000 100.73.48.81
                              └─ WSL2 BogdaRunner / dorm-x86 / 并发 1
                                      ↕ Prefect API + NAS CIFS
RK3528 100.78.158.80 ── Prefect :4200 / Bogda Console :3101 / Samba NAS
```

WSL 由 S4U 开机任务无登录启动（InteractiveToken 任务兜底）；Linux systemd 自动启动 worker 和 NAS 挂载。WSL 重启恢复已验证。宿舍网络掉线**不自动恢复**，需人工处理（疑为校园网门户认证）。3101 已按精确白名单开放写入（`allowlisted-test`/`owner`：两个 deployment + `dorm-x86`）；真实付费链可用（dsh 已装），研究任务实投待首次（任务单须满足开工包）。旧任务卡、雷达、exam-watch 操作仅供历史维护，当前均停用。

---

## 硬件（在役）

| 机器 | 规格 | 现在干什么 |
|---|---|---|
| 管理机 Windows | i7-11800H、64GB、3060 Laptop 12GB | 开发、SSH 管理、小试 CUDA；旧 3100 已停 |
| RK3528 | 4+128 Armbian | Prefect、pi-service 维护 worker、3101、Samba NAS 与备份；Tailscale 100.78.158.80 |
| 树莓派 4B | 2GB | **已空**，可断电。勿再当调度机 |
| 核桃派 1B | 1GB | 墨水屏 + 实验室冷备，不是执行节点 |
| Y7000 2021H | i5-11400H、16GB、Win10、512GB + 128GB | WSL2 Ubuntu / dorm-x86，SSH 100.73.48.81；并发 1 |

RK3528 数据在 **`/home/liuxfs/broker-data`**（`/mnt/broker` 指向该目录）。NAS：`\\10.77.0.1\nas` / Tailscale `\\100.78.158.80\nas`。Prefect：`http://10.77.0.1:4200`。

新宿舍主机采购仍暂停。现已使用 Y7000 接入 dorm-x86，硬件 RFC 留作历史参考。

---

## 挂账（状态以仓库+真机为准，不在此手抄 SHA）

- Skill digest：**owner 暂不锁**
- 旧 Orchestra 部署窗口转为历史挂账；当前不恢复旧 broker/exam-watch。
- Bogda Gate 6 与 Gate 7 S1/S2 历史验收通过；runner checkpoint 真机验收与落地接线（2026-09-11，含付费审批/usage-unknown/日志发布）已通过。
- Orchestra：2026-09-10 已停用 broker、雷达、exam-watch、旧冷备和 housekeeping，保留旧数据；共享 Bogda/NAS 服务继续运行。
- 4B 已空；Bogda 与 NAS 位于 RK3528。
- owner 已到校；手机热点下三机 Tailscale 互通，宿舍–实验室跨网络实测仍待做。
- 雷达→Zotero：9.8 后再设计
- 控制台：旧 3100 停用，Bogda 3101 在线（`allowlisted-test` + 精确白名单 + `owner`）；付费审批、recovery、日志发布已接线验收。
- 待拍板：SD 旧副本删除、512G SSD、宿舍 NAS、QQ bot、触发式 agent（盒子 `brief` 入队仍未接）。3101 聊天连 runner dsh **已否**
- 宿舍 runner：Y7000 已接入 dorm-x86；具体恢复命令、资源 ID、源码与真机差异见交接。
- 有意不做：全文证据扫描器、原子 `releases/<sha>`、Hermes / OpenClaw

---

## 历史往哪查

Mission 流水、验收数字、旧测试计数**不再维护于本文件**。

- 决策与时间线：`.tasks/completed/`、`orchestra/reports/`、`docs/reports/`
- 并发约定 / 模型路由 spec：`docs/superpowers/specs/2026-08-20-*.md`
- 学校网络：`orchestra/docs/school-network-switch.md`
- xju-desktop 属独立仓库 `wocessade/xju-portal-desktop`（本仓库仅引用设计 spec / 计划）

2026-08-18 起：总 spec → 4B Broker → 雷达四阶段 → 实验 ingest → 墨水屏 → Codex 副脑 → SOL 合并 → 3100 控制台 → 2026-08-22 锐评后门禁收紧、Hermes 放弃 → bogda 本地切片/受监督协调器 → exam-watch 上线 → 08-28 现网切 RK3528 → 08-31 Gate 6 通过 → 09-01 Gate 7 S1/S2 影子通过。
