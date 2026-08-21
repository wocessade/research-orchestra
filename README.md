# Research Orchestra

方向无关的科研**任务调度器**：Claude Code 编排，树莓派 4B Broker 7×24 跑队列，dsh/shell 执行，核桃派墨水屏 + 冷备，本机控制台 `http://127.0.0.1:3100/`。

它可靠的是「任务能不能跑完、产物会不会假绿」。它**不是**自主科研体——论文值不值得读、实验成不成立，仍由人 + LLM 当场判断。两份独立锐评（[`opus锐评.md`](opus锐评.md)、[`gpt-sol锐评.md`](gpt-sol锐评.md)）说的就是这件事；回复与下一步见 [`docs/reports/2026-08-22-critique-replies.md`](docs/reports/2026-08-22-critique-replies.md)。

运行手册：[`orchestra/README.md`](orchestra/README.md)。总 spec：[`docs/superpowers/specs/2026-08-18-research-orchestra-design.md`](docs/superpowers/specs/2026-08-18-research-orchestra-design.md)。教训库：[`docs/lessons-learned.md`](docs/lessons-learned.md)。不要把手写测试数、digest、部署 SHA 抄进本文档；以代码与 `check_skills.py --strict` 为准。

仓库：GitHub private `wocessade/research-orchestra`。

---

## 现在怎么跑

```
Windows CC / 3100 / 微信桥
        │ 任务卡 T-*.md
        ▼
4B Broker（2GB）队列 + dsh + 23:30 雷达四阶段
        │ POST /api/orchestra
        ▼
核桃派 usage-monitor 墨水屏 + 03:00 冷备
```

- 派任务：写卡 → `orchestra/scripts/sync_push.sh` → attempt 落盘 → `sync_pull`
- 雷达：`fetch → rank → render → notify`（五维评分权威；pipeline 六维只用于精读/归档）
- 实验入账：`run_card.py ingest`；`jsonschema` + `academic-shared` 的 `metrics.schema.json` **fail-closed**，且 schema 在 `skills.json` 契约里。改 skill 后必须审查再 `--lock-current --strict`，未锁定则 ingest HARD
- `rules.yaml`：**Broker 不读**；改了不会改调度。模型档位写在任务卡上，`model-routing.json` 给人/CC 查表，没有自动 resolver

阶段定位：基建够用，新工作优先论文/研究实体。入学 2026-09-08。

---

## 硬件（在役）

| 机器 | 规格 | 现在干什么 |
|---|---|---|
| Windows | i7-11800H、64GB、3060 Laptop 12GB | CC、3100、微信 iLink 桥、重计算 |
| 树莓派 4B | 2GB | Broker + dsh。冒烟峰值约 0.5GB，**不要再往这台塞 agent 循环** |
| 核桃派 1B | 1GB | 墨水屏 + 实验室冷备，不是执行节点 |

4B 数据在 `/mnt/broker`（闪迪 U 盘）。NAS：`\\192.168.0.250\nas` / Tailscale `\\100.111.75.58\nas`。

---

## 若要把调度重心转到 Hermes

**先定结果，再买机器。** 想要的结果如果是「手机用自然语言问进度、偶发派活」，那是 IM 值班面。想要的如果是「Hermes 取代 CC 写任务卡、取代 Broker 跑队列」，那是换产品，现有内核不要拆。

倒推：

1. **Broker 仍是作业内核。** Hermes 只多一层：读状态、必要时写卡或 SSH 注入。4B 继续跑 dispatcher/dsh。
2. **推理走云 API，本机不跑大模型。** 空转几乎不烧 token；对话、heartbeat、记忆压缩、工具轮会烧。
3. **微信过不了盒。** 现桥是 Windows iLink + fcc-server。Hermes 默认 Telegram/Discord。要微信：本机桥继续开，或另做 QQ（已暂缓）。
4. **4B 2GB 不合格。** 与 dsh 合住会抢内存、抢 OOM。核桃派 1GB 更不行。

**单独常驻盒最低档（API-only agent，不跑 Ollama/Playwright）：**

- 内存 **≥8GB**（16GB 更稳，给日志和偶发工具）
- 磁盘 **≥64GB SSD**
- CPU：N100 / 树莓派 5 **8GB** / 闲置 x86 笔电均可；不需要 GPU
- 网：7×24 + Tailscale；systemd 内存上限；禁止本机 LLM
- 只读 dashboard / `status.json`；**默认不写** `tasks/`、不碰 `inject_daily`

**还不够买的信号：** 没进组、方向未定、本机微信桥够用。触发条件仍是「IM 值班本机做不到，或 4B 内存再吃紧」。

总 spec §15 仍成立：不把 Orchestra **换成** Hermes；可以加一台盒子做通道。OpenClaw 仅在微信桥失效时再评。

---

## 挂账（状态以仓库+真机为准，不在此手抄 SHA）

- Skill digest：**owner 暂不锁**（ingest / `--strict` 会 HARD，直到明确开口 `--lock-current`）
- Pi / 核桃派部署窗口：四阶段雷达与相关 broker 修复的真机验证
- 入学前：宿舍–实验室 Tailscale 实测；核桃派 pi 密码
- 雷达→Zotero：9.8 后再设计
- 控制台 v1.5：tailnet 手机访问
- 待拍板：SD 旧副本删除、512G SSD、宿舍 NAS、QQ bot
- 锐评未做（有意）：`orchestra_check.py`、原子 `releases/<sha>` 发布、Task 未知字段全拒绝、Hermes 安装

---

## 历史往哪查

Mission 流水、验收数字、旧测试计数**不再维护于本文件**。

- 决策与时间线：`.tasks/completed/`、`orchestra/reports/`、`docs/reports/`
- 并发约定 / 模型路由 spec：`docs/superpowers/specs/2026-08-20-*.md`
- 学校网络：`orchestra/docs/school-network-switch.md`

2026-08-18 起：总 spec → 4B Broker → 雷达四阶段 → 实验 ingest → 墨水屏 → Codex 副脑 → SOL 合并 → 3100 控制台 → 2026-08-22 锐评后门禁收紧。
