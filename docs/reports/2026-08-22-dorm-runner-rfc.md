# 请 Opus / GPT-SOL 评：宿舍常驻 runner 与现网 Broker 怎么耦

作者：owner 侧（本机 CC 代写）。**只要评论合理性，不要改代码、不要扩 `orchestra_check`、不要提原子 `releases/<sha>`。** 回复请另开报告或在本文件末追加「评注」节；digest 仍未 `--lock-current`，勿代锁。

基线：Orchestra = 任务调度器（job runner + 夜间雷达），不是自主科研体。4B 继续当唯一队列。论文复现：CC 抽实验 → `T-*.md` → 有 GPU 的机器跑 → `metrics.json` ingest。**4B 不能无监督跑任意论文代码。**

---

## 1. 硬件分层（owner 已定，评耦合不要推翻分层）

| 层 | 谁 | 跑什么 |
|---|---|---|
| 笔记本 | i7-11800H / 64G / **3060 12GB**，跟人走 | 写卡、精读、小试 CUDA；**不能 7×24** |
| 4B Broker | 2GB，现网 `/home/liuxfs/broker-data` | 唯一队列：claim / 超时 / 重试 / 雷达；`executor` 现仅 `dsh\|shell` |
| 宿舍 runner（拟购） | 常驻 x86 + Ubuntu + Tailscale，**可后插 NVIDIA** | 过夜单卡复现、Docker 固定环境 |
| 组里服务器 | 人申请，**不自动 SSH 抢卡** | 多卡、>24GB、数天、保密数据 |

压缩预算（2026-08 国内公开行情，非成交单；50 系与内存在涨）：

- **0 元**：大活等组里，小活回家插电跑 3060。
- **~1.5–2.5k**：二手塔式（已带 32G DDR4）先无卡常驻，只解决离家。
- **~4.5–6.5k**：同上 + 二手 16/24G（A4000 或 3090）。显存升级的上限。
- **不要**：新迷你机 + Oculink + 新 5060 Ti 16G（8k–1.2 万且溢价）；不要 Mac。

**Hermes / IM 值班盒已放弃**（owner 2026-08-22），与本 RFC 无关。

---

## 2. 与旧系统的耦合原则

**Broker 不搬到 runner。** 盒子死只停实验，不停雷达和队列。

**控制台不派任务。** 3100 仍只读汇合面；派任务仍是 `T-*.md` → `sync_push` → 4B。留言的待决/告警**不驱动调度**（见下节事实，供你们核对）。

**现网字段不要先加。** `taskfile.py` 白名单里没有 `host` / `remote`。现在硬加 `executor: remote` 会让未部署的 4B 与已收紧的本机解析分叉。建议：

1. **P0（有盒子之前）**：约定写在卡正文或 CC 习惯——「本卡目标机：笔记本 / 宿舍 / 组里」。4B 只跑 `dsh`/`shell` 秒级活。GPU 卡先 **不要注入 4B**。
2. **P1（盒子已 SSH 通、手动跑通过 2–3 篇）**：再给 Broker 加一种执行器，例如 `executor: remote` + `host: dorm-runner`（名称进白名单，禁止任意 SSH 目标）。4B 用密钥以低权限用户执行**白名单命令**（`docker run …`），工作目录 `/data/jobs/<slug>/`，超时沿用卡上 `timeout`（1–86400）。产物约定仍落 `attempt-N/`：`metrics.json` 由 4B 拉回或 runner 推到 `result` 相对路径，**ingest 契约不变**（缺 jsonschema / digest 未锁仍 HARD）。
3. **组里**：只备忘「如何申请、数据能否出校、结果如何拷回 ingest」。不要做集群客户端。

Runner 软件最小集：无桌面 Ubuntu、Docker（有卡后再加 NVIDIA toolkit）、用户 `runner` 无随意 sudo、默认断外网（拉数据集再临时开）。

成功标准仍是实验卡 `metrics.json` + ingest，不是模型自称复现。

---

## 3. 请评的问题（请逐条给同意 / 反对 / 改法）

1. **队列唯一在 4B、GPU 在宿舍**，用 SSH 白名单当执行器，是否比「runner 上再跑一个 Broker」更少分叉？后者挂了谁接管 claim？
2. **P0 禁止 GPU 卡注入 4B**（靠人/CC 纪律）是否太软？有没有低成本硬闸（例如 `shell` 体里出现 `nvidia-smi`/`docker` 直接 invalid）值得做，还是会误伤雷达/运维卡？
3. 新字段是 `executor: remote` + `host:`，还是 `executor: shell` 加 `runtime: dorm`？未知字段现网已全拒绝，加字段等于一次全模板回归。
4. 宿舍 12G 与笔记本 3060 同档时，常驻盒是否仍有价值（只换「人走还在」）？还是必须 16/24G 才值得买？
5. 产物回传：runner 写完由 4B `scp` 拉，还是 runner 反向 `scp` 到 `broker-data/results`？哪边失败语义更干净（超时、部分落盘、attempt 原子）？
6. 这套是否又在堆基建、偏离「入学后先出论文」？若你们认为 **0 元 + 组里卡** 才合理，请直说。

---

## 4. 明确不在本讨论范围

换产品名；OpenClaw；Hermes；把 `rules.yaml` 接进 dispatcher；手机控制台 v1.5；雷达→Zotero。
