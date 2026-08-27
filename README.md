# Research Orchestra

方向无关的科研**任务调度器**：Claude Code 编排，树莓派 4B Broker 7×24 跑队列，dsh/shell 执行，核桃派墨水屏 + 冷备，本机控制台 `http://127.0.0.1:3100/`。

它可靠的是「任务能不能跑完、产物会不会假绿」。它**不是**自主科研体。锐评原文 `opus锐评.md` / `gpt-sol锐评.md` 已于 2026-08-28 移除；当时回复见 [`docs/reports/2026-08-22-critique-replies.md`](docs/reports/2026-08-22-critique-replies.md)。

**bogda 是继任者**（Prefect based，[`bogda/`](bogda/README.md)）：本地纵向切片可通过、受监督协调器在 batched 分支演进；现网执行仍是 `orchestra/`（4B Broker）。新任务优先论文/研究实体，纯基建只记挂账。

运行手册：[`orchestra/README.md`](orchestra/README.md)。总 spec：[`docs/superpowers/specs/2026-08-18-research-orchestra-design.md`](docs/superpowers/specs/2026-08-18-research-orchestra-design.md)。教训库：[`docs/lessons-learned.md`](docs/lessons-learned.md)。不要把手写测试数、digest、部署 SHA 抄进本文档。

仓库：GitHub private `wocessade/research-orchestra`。

---

## 现在怎么跑

```
Windows CC / 3100 / 微信桥
        │ 任务卡 T-*.md
        ▼
4B Broker（2GB，broker-data）队列 + dsh + 23:30 雷达四阶段 + exam-watch 考试定时
        │ POST /api/orchestra + exam 告警/心跳
        ▼
核桃派 usage-monitor 墨水屏 + 03:00 冷备
```

- 派任务：写卡 → `orchestra/scripts/sync_push.sh` → attempt 落盘 → `sync_pull`（默认 `ORCHESTRA_REMOTE_ROOT=/home/liuxfs/broker-data`）
- 雷达：`fetch → rank → render → notify`（五维评分权威；pipeline 六维只用于精读/归档）
- 实验入账：`run_card.py ingest`；缺 jsonschema / schema / 未锁 digest → HARD
- `rules.yaml`：**Broker 不读**。模型档位写在任务卡上
- 雨课堂考试：4B `orchestra-exam-watch.timer` 轮询 → `exam_alert.json`/`exam_watch_beat.json` → 控制台告警/留言融合

阶段定位：基建够用，新工作优先论文。入学 2026-09-08。

---

## 硬件（在役）

| 机器 | 规格 | 现在干什么 |
|---|---|---|
| Windows | i7-11800H、64GB、3060 Laptop 12GB | CC、3100、微信 iLink 桥、小试 CUDA（跟人走） |
| 树莓派 4B | 2GB | Broker + dsh + exam-watch。冒烟峰值约 0.5GB，**不要再往这台塞 agent 循环** |
| 核桃派 1B | 1GB | 墨水屏 + 实验室冷备，不是执行节点 |

4B 数据在 **`/home/liuxfs/broker-data`**。`/mnt/broker` 是旧 U 盘路径，未挂不要 scp。NAS：`\\192.168.0.250\nas` / Tailscale `\\100.111.75.58\nas`。

拟购宿舍 runner 与组里溢出：见 [`docs/reports/2026-08-22-dorm-runner-rfc.md`](docs/reports/2026-08-22-dorm-runner-rfc.md)，未拍板。

---

## 挂账（状态以仓库+真机为准，不在此手抄 SHA）

- Skill digest：**owner 暂不锁**
- 4B 部署窗口：`deploy_broker.sh` 已含 exam-watch 传载/启用，实例上 env.conf 需手工复制（脚本 WARN）
- bogda Gate 6 复测：trial `20260827T124429Z` 跑满 72h 窗口（→ 2026-08-30T12:44Z）；USB `Requires=mnt-nas.mount` 为已知缺口
- 入学前（2026-09-08）：宿舍–实验室 Tailscale 实测；核桃派 pi 密码
- 雷达→Zotero：9.8 后再设计
- 控制台 v1.5：tailnet 手机访问
- 待拍板：SD 旧副本删除、512G SSD、宿舍 NAS、QQ bot、宿舍 runner 三档预算
- 有意不做：全文证据扫描器、原子 `releases/<sha>`、Hermes / OpenClaw

---

## 历史往哪查

Mission 流水、验收数字、旧测试计数**不再维护于本文件**。

- 决策与时间线：`.tasks/completed/`、`orchestra/reports/`、`docs/reports/`
- 并发约定 / 模型路由 spec：`docs/superpowers/specs/2026-08-20-*.md`
- 学校网络：`orchestra/docs/school-network-switch.md`
- xju-desktop 属独立仓库 `wocessade/xju-portal-desktop`（本仓库仅引用设计 spec / 计划）

2026-08-18 起：总 spec → 4B Broker → 雷达四阶段 → 实验 ingest → 墨水屏 → Codex 副脑 → SOL 合并 → 3100 控制台 → 2026-08-22 锐评后门禁收紧、Hermes 放弃 → bogda 本地切片/受监督协调器 → exam-watch 上线 → 08-27 Gate 6 收口复测中。
