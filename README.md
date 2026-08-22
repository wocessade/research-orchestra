# Research Orchestra

方向无关的科研**任务调度器**：Claude Code 编排，树莓派 4B Broker 7×24 跑队列，dsh/shell 执行，核桃派墨水屏 + 冷备，本机控制台 `http://127.0.0.1:3100/`。

它可靠的是「任务能不能跑完、产物会不会假绿」。它**不是**自主科研体。锐评原文 [`opus锐评.md`](opus锐评.md)、[`gpt-sol锐评.md`](gpt-sol锐评.md)；当时回复 [`docs/reports/2026-08-22-critique-replies.md`](docs/reports/2026-08-22-critique-replies.md)。

运行手册：[`orchestra/README.md`](orchestra/README.md)。总 spec：[`docs/superpowers/specs/2026-08-18-research-orchestra-design.md`](docs/superpowers/specs/2026-08-18-research-orchestra-design.md)。教训库：[`docs/lessons-learned.md`](docs/lessons-learned.md)。不要把手写测试数、digest、部署 SHA 抄进本文档。

仓库：GitHub private `wocessade/research-orchestra`。

---

## 今晚请 Opus / GPT-SOL 复核（2026-08-22 夜）

**只要评合理性与是否漏账，不要改代码、不要 `--lock-current`、不要提 Hermes / OpenClaw / 原子 `releases/<sha>`。** 宿舍 runner 耦合六问仍在 [`docs/reports/2026-08-22-dorm-runner-rfc.md`](docs/reports/2026-08-22-dorm-runner-rfc.md)；评注可开新报告或写在 RFC 末。

### 已定调

- 产品就是 job runner + 夜间雷达，不是自主科研。论文值不值得读、实验成不成立，仍由人 + 当场 LLM 判断。
- 【术】够用，转入【道】：新任务优先论文/研究实体；纯基建只记挂账。
- **Hermes 扔掉**：不做 IM 值班盒，不替代 Broker，不写采购倒推。微信桥继续留在 Windows。4B 仍是唯一队列。
- 笔记本（3060 12GB）跟人走，不能 7×24；大活问组里要卡。宿舍常驻 runner 若买：x86 + Ubuntu + 可后插 NVIDIA，预算心里锚 **0 / ~2k 无卡塔 / ~5–6k+16G**。Mac / 新迷你机+Oculink+溢价 16G 新卡不买。
- 4B **不能**无监督跑任意论文代码。GPU 卡先不要注入 Broker。

### 进度（相对锐评基线 `39d284a` / `56a84f3`）

| 项 | 状态 |
|---|---|
| ingest schema fail-closed；`academic-shared` 进 digest 契约 | 仓库已做。**digest 未锁**（故意），`--strict` / 真 ingest 仍 HARD |
| `rules.yaml` 标明 Broker 不读 | 已做 |
| `orchestra/results` 脱索引 | 已做 |
| 对外 README 改诚实 | 已做 |
| 4B 现网数据根 | **`/home/liuxfs/broker-data`**（U 盘 `/mnt/broker` 未挂）。本机 `sync_pull` / 控制台 refresh 默认已改到这里 |
| 四阶段雷达 | 本机代码 + 8-22 补跑 catch-up 已 `done`；Pi 上 parser 收紧等仍要下次 deploy |
| 任务卡解析 | 本机 `taskfile.py` 拒绝未知字段、重复 key、timeout 越界、`model` 非 flash\|pro。**尚未 redeploy 到 4B** |
| 薄 `orchestra_check.py` | 本机：unittest + `check_skills --strict` + tracked-ignored。不是全文证据扫描器 |
| 控制台 3100 | 告警/最新由 refresh 派生；待决首页可写可撤；月历与日程同高。**不派任务**。新 agent 不会自动当必经入口 |
| 宿舍 runner | 只到 RFC，未采购、未加 `executor: remote` |

### 请你们盯的缺口

1. RFC §3 六问（队列唯一在 4B vs runner 再跑 Broker；P0 禁 GPU 注入是否太软；字段怎么加；12G 常驻有没有价值；产物谁 scp；是否不该再买盒子）。
2. 本机 taskfile 已严、4B 仍宽：分叉是否必须下次部署窗口一次对齐。
3. digest 继续不锁是否可接受（owner 暂不锁）。

---

## 现在怎么跑

```
Windows CC / 3100 / 微信桥
        │ 任务卡 T-*.md
        ▼
4B Broker（2GB，broker-data）队列 + dsh + 23:30 雷达四阶段
        │ POST /api/orchestra
        ▼
核桃派 usage-monitor 墨水屏 + 03:00 冷备
```

- 派任务：写卡 → `orchestra/scripts/sync_push.sh` → attempt 落盘 → `sync_pull`（默认 `ORCHESTRA_REMOTE_ROOT=/home/liuxfs/broker-data`）
- 雷达：`fetch → rank → render → notify`（五维评分权威；pipeline 六维只用于精读/归档）
- 实验入账：`run_card.py ingest`；缺 jsonschema / schema / 未锁 digest → HARD
- `rules.yaml`：**Broker 不读**。模型档位写在任务卡上

阶段定位：基建够用，新工作优先论文。入学 2026-09-08。

---

## 硬件（在役）

| 机器 | 规格 | 现在干什么 |
|---|---|---|
| Windows | i7-11800H、64GB、3060 Laptop 12GB | CC、3100、微信 iLink 桥、小试 CUDA（跟人走） |
| 树莓派 4B | 2GB | Broker + dsh。冒烟峰值约 0.5GB，**不要再往这台塞 agent 循环** |
| 核桃派 1B | 1GB | 墨水屏 + 实验室冷备，不是执行节点 |

4B 数据在 **`/home/liuxfs/broker-data`**。`/mnt/broker` 是旧 U 盘路径，未挂不要 scp。NAS：`\\192.168.0.250\nas` / Tailscale `\\100.111.75.58\nas`。

拟购宿舍 runner 与组里溢出：见 RFC，未拍板。

---

## 挂账（状态以仓库+真机为准，不在此手抄 SHA）

- Skill digest：**owner 暂不锁**
- Pi 再部署：taskfile 收紧、artifact 校验、taskkill 树杀等与仓库对齐
- 入学前：宿舍–实验室 Tailscale 实测；核桃派 pi 密码
- 雷达→Zotero：9.8 后再设计
- 控制台 v1.5：tailnet 手机访问
- 待拍板：SD 旧副本删除、512G SSD、宿舍 NAS、QQ bot、宿舍 runner 三档预算
- 有意不做：全文 `orchestra_check` 扫 Markdown、原子 `releases/<sha>`、Hermes / OpenClaw

---

## 历史往哪查

Mission 流水、验收数字、旧测试计数**不再维护于本文件**。

- 决策与时间线：`.tasks/completed/`、`orchestra/reports/`、`docs/reports/`
- 并发约定 / 模型路由 spec：`docs/superpowers/specs/2026-08-20-*.md`
- 学校网络：`orchestra/docs/school-network-switch.md`

2026-08-18 起：总 spec → 4B Broker → 雷达四阶段 → 实验 ingest → 墨水屏 → Codex 副脑 → SOL 合并 → 3100 控制台 → 2026-08-22 锐评后门禁收紧 → 控制台汇合面可用、Hermes 放弃。
