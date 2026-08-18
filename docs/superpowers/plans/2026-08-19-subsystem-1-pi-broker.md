# Subsystem 1: Pi Broker + dsh 执行层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在树莓派 4B 上部署常驻任务代理（Broker：队列/dispatcher/checkpoint/恢复）+ dsh 执行层，跑通"Windows 派任务 → Broker 执行 → 结果落盘 → Windows 复查"闭环，并以 2GB 内存冒烟测试作为 Pi 5 升级决策门。

**Architecture:** Broker 为纯 Python stdlib 守护进程（SQLite WAL 状态库 + 任务文件轮询 + dsh/shell 双执行器 + systemd 常驻）。任务文件是唯一派发入口（CC 写 → scp 推 → Broker 轮询执行 → 增量写 attempt 目录 → 状态入库）；Windows 与本机无 git remote/sshd/rsync（已核实），**v1 同步总线用 scp**，Windows 侧 git 负责版本化（偏离总 spec §4"git 同步总线"的原因见 DECISIONS 021）。

**Tech Stack:** Python 3.11 stdlib only（sqlite3/subprocess/unittest）、dsh 0.1.0-rc.7（npm 全局）、systemd、scp、Git Bash。

## Global Constraints

- Broker 代码零 pip 依赖（Pi 不装包）；测试框架用 `unittest`（非 pytest）
- dsh 锁版本：`@deepseek-ai/dsh@0.1.0-rc.7`（npm 安装命令中显式指定）
- 4B 用户 `liuxfs`；broker 数据根 `/mnt/broker/`（SSD 挂载点）；代码目录 `/home/liuxfs/broker/`
- 密钥/凭据/TODO 不入 git：`config.json`（含 monitor_token）在 Pi 本地创建，仓库只提交 `config.example.json`
- commit 不加 Co-Authored-By 署名行
- 不动 `~/.claude/settings.json`；不动核桃派上在役的 usage-monitor 服务
- Windows 侧测试一律在 Git Bash 下运行：`python -m unittest discover`
- 任务文件格式严格（§5 模板）：头部 `key: value` 行，`---` 分隔符后为执行体

---

### Task 1: orchestra 文件夹骨架 + 任务模板 + scp 同步脚本（Windows）

**Files:**
- Create: `D:\pythonProject\orchestra\README.md`
- Create: `D:\pythonProject\orchestra\config\rules.yaml`
- Create: `D:\pythonProject\orchestra\tasks\.gitkeep`
- Create: `D:\pythonProject\orchestra\results\.gitkeep`
- Create: `D:\pythonProject\orchestra\logs\.gitkeep`
- Create: `D:\pythonProject\orchestra\reports\.gitkeep`
- Create: `D:\pythonProject\orchestra\done\.gitkeep`
- Create: `D:\pythonProject\orchestra\scripts\sync_push.sh`
- Create: `D:\pythonProject\orchestra\scripts\sync_pull.sh`
- Create: `D:\pythonProject\orchestra\broker\__init__.py`（空文件，标记 broker 代码归属）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces: `orchestra/tasks/`（任务入口）、`orchestra/results/`、`orchestra/scripts/sync_push.sh|sync_pull.sh`（依赖环境变量 `ORCHESTRA_SSH_HOST`、`ORCHESTRA_SSH_USER`，默认 `liuxfs`）——Task 11 端到端验收直接调用

- [ ] **Step 1: 创建目录骨架**

```bash
cd /d/pythonProject && mkdir -p orchestra/{config,tasks,results,logs,reports,done,scripts,broker}
touch orchestra/{tasks,results,logs,reports,done}/.gitkeep orchestra/broker/__init__.py
```

- [ ] **Step 2: 写 README.md**

```markdown
# Orchestra — 科研编排调度中枢

以 Claude Code 为核心的科研-实验-论文框架（总 spec：docs/superpowers/specs/2026-08-18-research-orchestra-design.md）。

| 目录 | 用途 |
|------|------|
| config/rules.yaml | 执行器分派规则与降级顺序（CC 分派前读） |
| config/model-routing.md | 模型调度策略表（用户维护，系统只读） |
| tasks/ | 任务文件总线：CC 写入，Broker 轮询 |
| results/ | 执行器产出（attempt-N/ 目录：stdout/stderr/state.json） |
| logs/ | broker.log 与执行日志 |
| reports/ | CC 复查记录 |
| done/ | 归档 |
| scripts/ | sync_push.sh / sync_pull.sh（scp 同步） |
| broker/ | Broker 源码（stdlib only，scp 部署到 4B） |

任务文件格式（严格）：

    # T-YYYYMMDD-<slug>
    executor: dsh | shell
    net: required | optional
    result: results/T-YYYYMMDD-<slug>
    timeout: <秒，默认 3600>
    ---
    <执行体：dsh 任务的 prompt 全文，或 shell 任务的命令>

快速流程：写 tasks/T-*.md → sync_push.sh → 等 Broker 执行 → sync_pull.sh → CC 复查写 reports/ → 归档 done/。
```

- [ ] **Step 3: 写 rules.yaml**

```yaml
# 执行器分派规则（v1）
default_executor: dsh          # 未显式指定时默认
executors:
  dsh:                         # 4B 上的 dsh headless（主执行器）
    net: required              # 需要外网（LLM API）
    host: pi4                  # 目标主机标识
  shell:                       # 本地 shell 命令（Pi 侧执行）
    net: optional              # 断网照跑
  codex: disabled              # subsystem-3 启用
  haiku: cc-side               # CC 子代理，不经 Broker（subsystem-5 细化）
max_attempts: 2                # 失败重试上限（Broker 同值，见 config.example.json）
degradation_order: [pi-dsh, win-dsh, direct]
  # win-dsh = Windows 本地 dsh（手动降级，Task 2 安装）；direct = CC 直接 Bash
```

- [ ] **Step 4: 写 sync_push.sh**

```bash
#!/usr/bin/env bash
# 推送 tasks/ 下全部任务文件到 4B Broker（幂等：Broker 按 slug 去重）
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash sync_push.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
shopt -s nullglob
files=("$ROOT"/tasks/T-*.md)
if [ ${#files[@]} -eq 0 ]; then
  echo "无待推送任务（tasks/ 下没有 T-*.md）"
  exit 0
fi
scp -q "${files[@]}" "$SSH_USER@$SSH_HOST:/mnt/broker/tasks/"
echo "已推送 ${#files[@]} 个任务文件"
```

- [ ] **Step 5: 写 sync_pull.sh**

```bash
#!/usr/bin/env bash
# 从 4B Broker 拉取 results/ 与 logs/（增量覆盖本地同名文件）
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash sync_pull.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
scp -rq "$SSH_USER@$SSH_HOST:/mnt/broker/results/." "$ROOT/results/"
scp -rq "$SSH_USER@$SSH_HOST:/mnt/broker/logs/." "$ROOT/logs/"
echo "已拉取 results/ 与 logs/"
```

- [ ] **Step 6: 验证**

```bash
cd /d/pythonProject/orchestra && bash -n scripts/sync_push.sh && bash -n scripts/sync_pull.sh && echo "语法 OK"
ORCHESTRA_SSH_HOST=127.0.0.1 bash scripts/sync_push.sh 2>&1 | head -3
# 期望：连接失败报错（127.0.0.1 无 sshd）或"无待推送任务"——两种输出都证明脚本可用；不产生任何文件改动
```

- [ ] **Step 7: Commit**

```bash
cd /d/pythonProject && git add orchestra/ && git commit -m "feat: add orchestra folder skeleton, task template, scp sync scripts"
```

### Task 2: Windows 本地 dsh 安装 + headless 冒烟（降级执行器）

**Files:**
- 无仓库文件改动（全局 npm 安装）

**Interfaces:**
- Consumes: 无
- Produces: 全局命令 `dsh`（Windows）——Task 5/11 的降级执行器；验证过的 headless 调用模式 `dsh --profile headless "<任务文本>"`

- [ ] **Step 1: 安装（锁版本）**

```bash
npm install -g @deepseek-ai/dsh@0.1.0-rc.7
dsh --version
```
Expected: 输出 0.1.0-rc.7（或含该版本号的一行）

- [ ] **Step 2: 配置模型凭据（Web UI 一次性）**

```bash
dsh web
```
浏览器打开 http://127.0.0.1:3080 → Settings → Models → 填 DeepSeek API Key（选 DeepSeek 目录供应商，模型如 deepseek-chat）→ 关闭浏览器与 `dsh web` 进程。
**注意**：凭据写入 `$DSH_HOME/.credentials.yaml`（只写文件），绝不复制内容、绝不入 git。

- [ ] **Step 3: headless 冒烟**

```bash
dsh --profile headless "运行 python --version 并把输出原样报告给我"
```
Expected: 最终答案包含 Python 版本号，进程退出码 0。

- [ ] **Step 4: 记录降级路径验证**

```bash
dsh --profile headless "echo broker-fallback-ok"
```
Expected: 输出包含 broker-fallback-ok，退出码 0。至此 Windows 本地 dsh 成为可用的降级执行器（degradation_order 第二级）。

- [ ] **Step 5: Commit（无文件改动则跳过）**

```bash
cd /d/pythonProject && git status --short && echo "无仓库改动，无需提交"
```

### Task 3: 4B 的 2280 SSD 挂载（/mnt/broker）

**Files:**
- Modify: `/etc/fstab`（4B 侧，非仓库文件）
- Create: `/mnt/broker/{tasks,results,logs,db}/`（4B 侧目录）

**Interfaces:**
- Consumes: 无（硬件任务）
- Produces: 挂载点 `/mnt/broker`（后续所有 broker 数据根，config.json 的绝对路径引用它）

- [ ] **Step 1: 物理接入 + 识别**

用户将 2280 SSD 装入 USB3 M.2 转接盒并插入 4B USB3 口。然后：

```bash
ssh liuxfs@<4B_IP> lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E "sd|mmc"
```
Expected: 出现一个 ~<SSD 容量> 的 `sdX` 块设备（未挂载）。记录设备名（下文以 `/dev/sda` 为例，按实际替换）。

- [ ] **Step 2: 分区与格式化**

```bash
ssh liuxfs@<4B_IP> 'sudo fdisk /dev/sda <<< $'"'"'g\nn\n\n\n\nw'"'"' && sudo mkfs.ext4 -L broker-data /dev/sda1'
```
Expected: mkfs.ext4 输出 "Writing superblocks and filesystem accounting information: done"

- [ ] **Step 3: 挂载 + 目录 + fstab 持久化**

```bash
ssh liuxfs@<4B_IP> 'sudo mkdir -p /mnt/broker && sudo mount /dev/sda1 /mnt/broker && \
  UUID=$(sudo blkid -s UUID -o value /dev/sda1) && \
  echo "UUID=$UUID /mnt/broker ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab && \
  sudo chown liuxfs:liuxfs /mnt/broker && \
  mkdir -p /mnt/broker/{tasks,results,logs,db} && \
  df -h /mnt/broker && cat /etc/fstab | grep broker'
```
Expected: `df -h` 显示 /mnt/broker 为 SSD 容量；fstab 末行含 UUID。

- [ ] **Step 4: 重启持久性验证**

```bash
ssh liuxfs@<4B_IP> 'sudo reboot' && sleep 45 && ssh liuxfs@<4B_IP> 'df -h /mnt/broker && ls /mnt/broker/'
```
Expected: 重启后 /mnt/broker 仍挂载，四个子目录（tasks/results/logs/db）存在。

### Task 4: 4B 安装 Node ≥22.19

**Files:**
- Create: `/opt/node-<版本>/`（4B 侧系统文件）
- Modify: `~/.bashrc`（4B 侧，追加 PATH）

**Interfaces:**
- Consumes: 无
- Produces: 4B 上的 `node`/`npm`（≥22.19）——Task 5 dsh 安装的前置

- [ ] **Step 1: 确认架构与 OS**

```bash
ssh liuxfs@<4B_IP> 'uname -m && cat /etc/os-release | grep -E "^(PRETTY_NAME|VERSION_CODENAME)"'
```
Expected: `aarch64`（若输出 `armv7l` 见 Step 1b）。Debian/Raspberry Pi OS 12（bookworm）。

- [ ] **Step 1b: 仅 armv7l 分支——重刷 64 位系统（决策门）**

若 `uname -m` 输出 armv7l：Node 新版本对 32 位 arm 支持不稳定，且 dsh 未在 32 位验证。**暂停并上报用户**（Trigger Report 场景），重刷 Raspberry Pi OS (64-bit) lite 后再继续。不在此任务内自行刷机。

- [ ] **Step 2: 下载 arm64 最新 v22 LTS tarball（动态解析版本号，不硬编码）**

```bash
VER=$(curl -s https://nodejs.org/dist/latest-v22.x/ | grep -o 'node-v22[^"]*linux-arm64.tar.xz' | head -1)
echo "版本: $VER"
ssh liuxfs@<4B_IP> "curl -fsSL -o /tmp/$VER https://nodejs.org/dist/latest-v22.x/$VER"
```
Expected: `VER` 形如 `node-v22.XX.X-linux-arm64.tar.xz`（v22 最新版）；Pi 上文件下载完成无报错。

- [ ] **Step 3: 解压安装到 /opt 并验证版本**

```bash
ssh liuxfs@<4B_IP> "VER=$VER; sudo tar -xJf /tmp/\$VER -C /opt && sudo ln -sfn /opt/\${VER%.tar.xz} /opt/node22 && echo 'export PATH=/opt/node22/bin:\$PATH' >> ~/.bashrc && export PATH=/opt/node22/bin:\$PATH && node --version && npm --version"
```
Expected: `node --version` 输出 ≥ v22.19.0，npm 输出 ≥ 10。

### Task 5: 4B 安装 dsh + 2GB 冒烟决策门

**Files:**
- 4B 侧全局 npm 包 + `$DSH_HOME` 凭据（不入库）

**Interfaces:**
- Consumes: Task 4 的 node/npm
- Produces: 4B 的 `dsh` 全局命令；**决策门结论（GO/NO-GO 记录 DECISIONS）**——GO 则 Task 6-11 继续；NO-GO 则暂停并上报（§14 Pi 5 采购）

- [ ] **Step 1: 安装（锁版本）**

```bash
ssh liuxfs@<4B_IP> 'export PATH=/opt/node22/bin:$PATH && npm install -g @deepseek-ai/dsh@0.1.0-rc.7 && dsh --version'
```
Expected: 版本输出 0.1.0-rc.7。

- [ ] **Step 2: 配置凭据**

```bash
ssh liuxfs@<4B_IP> 'export PATH=/opt/node22/bin:$PATH && dsh web --host 0.0.0.0 2>&1 | head -3'
```
（若无 `--host` 参数则本机端口转发访问）通过浏览器或 SSH 端口转发打开 Web UI，Settings→Models 填 DeepSeek API Key（同 Task 2 的 key）。完成后 Ctrl+C 结束。**凭据文件权限**：`chmod 600 $DSH_HOME/.credentials.yaml`（若存在）。

- [ ] **Step 3: 冒烟任务 + 内存采样（决策门核心）**

```bash
ssh liuxfs@<4B_IP> 'export PATH=/opt/node22/bin:$PATH && \
  ( for i in $(seq 1 60); do free -m | awk -v i=$i "NR==2{print i\" \"\$3}"; sleep 2; done > /tmp/mem-samples.txt & \
    SAMPLER=$!; \
    time dsh --profile headless "运行 python3 --version 并原样报告"; RC=$?; \
    kill $SAMPLER 2>/dev/null; \
    echo EXIT_CODE=$RC; sort -t" " -k2 -n -r /tmp/mem-samples.txt | head -3 )'
```
Expected: EXIT_CODE=0，且输出含 Python 版本号。记录内存峰值 = `sort` 输出的第一行第二列（MiB）。

- [ ] **Step 4: 判定**

```bash
ssh liuxfs@<4B_IP> 'dmesg | grep -i "out of memory" | tail -3 || echo "无 OOM 事件"'
```
- **GO 标准**：EXIT_CODE=0 且 峰值 ≤ 1536 MiB 且 无 OOM 事件，且 **重复 Step 3 共 3 次全部满足** → 在 DECISIONS.md 记录 `GO: dsh 2GB 冒烟通过（峰值 NNN MiB）`，继续 Task 6。
- **NO-GO**：任一不满足 → 在 DECISIONS.md 记录实测数据，**立即暂停并上报用户**（按 §14 触发 Pi 5 8GB 采购评估）。

- [ ] **Step 5: 清理采样文件**

```bash
ssh liuxfs@<4B_IP> 'rm -f /tmp/mem-samples.txt'
```

### Task 6: broker/db.py — SQLite WAL 状态库

**Files:**
- Create: `D:\pythonProject\orchestra\broker\db.py`
- Test: `D:\pythonProject\orchestra\broker\tests\test_db.py`

**Interfaces:**
- Consumes: 无
- Produces（后续任务依赖的精确签名）:
  - `init_db(db_path) -> sqlite3.Connection`
  - `register_task(conn, slug, net_req, result_path)`（INSERT OR IGNORE，幂等）
  - `claim_task(conn, slug) -> bool`（queued→running，attempts+1；已被抢返回 False）
  - `finish_task(conn, slug, status, error=None)`
  - `requeue_failed(conn, max_attempts) -> int`（failed 且 attempts<max → queued）
  - `recover_running(conn) -> int`（running→failed，error='recovered after restart'）
  - `list_tasks(conn, status=None) -> list[tuple(slug, status, attempts, net_req, error)]`

- [ ] **Step 1: 写失败测试** `orchestra/broker/tests/test_db.py`

```python
"""db.py 单元测试（stdlib unittest，tempfile 隔离）。"""
import os
import tempfile
import unittest

import db  # noqa: E402  （tests 与 db.py 同目录时由 discover 解析）

class TestDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(os.path.join(self.tmp.name, "broker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_register_is_idempotent(self):
        db.register_task(self.conn, "T-001", "optional", "results/T-001")
        db.register_task(self.conn, "T-001", "optional", "results/T-001")
        self.assertEqual(len(db.list_tasks(self.conn)), 1)

    def test_claim_finish_flow(self):
        db.register_task(self.conn, "T-001", "required", "r")
        self.assertTrue(db.claim_task(self.conn, "T-001"))
        self.assertFalse(db.claim_task(self.conn, "T-001"))  # 不可重复抢
        self.assertEqual(db.list_tasks(self.conn, "running")[0][0], "T-001")
        db.finish_task(self.conn, "T-001", "done")
        row = db.list_tasks(self.conn, "done")[0]
        self.assertEqual(row[0], "T-001")
        self.assertEqual(row[4], None)  # error 为空

    def test_finish_failed_with_error(self):
        db.register_task(self.conn, "T-002", "optional", "r")
        db.claim_task(self.conn, "T-002")
        db.finish_task(self.conn, "T-002", "failed", "exit code 1")
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][4], "exit code 1")

    def test_requeue_failed_respects_max_attempts(self):
        db.register_task(self.conn, "T-003", "optional", "r")
        db.claim_task(self.conn, "T-003")
        db.finish_task(self.conn, "T-003", "failed", "x")
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=1), 0)  # attempts=1 不重试
        db.requeue_failed(self.conn, max_attempts=2)
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=2), 1)  # 回 queued
        db.claim_task(self.conn, "T-003")
        db.finish_task(self.conn, "T-003", "failed", "y")
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=2), 0)  # attempts=2 终态

    def test_recover_running(self):
        db.register_task(self.conn, "T-004", "optional", "r")
        db.claim_task(self.conn, "T-004")
        n = db.recover_running(self.conn)
        self.assertEqual(n, 1)
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][4], "recovered after restart")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_db.py" -v 2>&1 | tail -3
```
Expected: FAIL（`ModuleNotFoundError: No module named 'db'`）

- [ ] **Step 3: 写实现** `orchestra/broker/db.py`

```python
"""Broker 任务状态库：SQLite WAL，stdlib only。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    slug TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed
    attempts INTEGER NOT NULL DEFAULT 0,
    net_req TEXT NOT NULL DEFAULT 'optional',
    result_path TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    done_at TEXT
);
"""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    conn.commit()
    return conn

def register_task(conn: sqlite3.Connection, slug: str, net_req: str, result_path: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO tasks (slug, net_req, result_path, created_at) VALUES (?,?,?,?)",
        (slug, net_req, result_path, _now()),
    )
    conn.commit()

def claim_task(conn: sqlite3.Connection, slug: str) -> bool:
    cur = conn.execute(
        "UPDATE tasks SET status='running', started_at=?, attempts=attempts+1, error=NULL "
        "WHERE slug=? AND status='queued'",
        (_now(), slug),
    )
    conn.commit()
    return cur.rowcount == 1

def finish_task(conn: sqlite3.Connection, slug: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE tasks SET status=?, done_at=?, error=? WHERE slug=?",
        (status, _now(), error, slug),
    )
    conn.commit()

def requeue_failed(conn: sqlite3.Connection, max_attempts: int) -> int:
    n = conn.execute(
        "UPDATE tasks SET status='queued', error=NULL WHERE status='failed' AND attempts < ?",
        (max_attempts,),
    ).rowcount
    conn.commit()
    return n

def recover_running(conn: sqlite3.Connection) -> int:
    n = conn.execute(
        "UPDATE tasks SET status='failed', done_at=?, error='recovered after restart' "
        "WHERE status='running'",
        (_now(),),
    ).rowcount
    conn.commit()
    return n

def list_tasks(conn: sqlite3.Connection, status: str | None = None) -> list[tuple]:
    if status:
        return conn.execute(
            "SELECT slug, status, attempts, net_req, error FROM tasks WHERE status=?",
            (status,),
        ).fetchall()
    return conn.execute(
        "SELECT slug, status, attempts, net_req, error FROM tasks"
    ).fetchall()
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_db.py" -v 2>&1 | tail -3
```
Expected: `OK`（5 tests passed）

- [ ] **Step 5: Commit**

```bash
cd /d/pythonProject && git add orchestra/broker/ && git commit -m "feat: broker db module - SQLite WAL task state with tests"
```

### Task 7: broker/taskfile.py — 任务文件解析

**Files:**
- Create: `D:\pythonProject\orchestra\broker\taskfile.py`
- Test: `D:\pythonProject\orchestra\broker\tests\test_taskfile.py`

**Interfaces:**
- Consumes: 无（Task 6 的 db 不相关）
- Produces:
  - `@dataclass TaskSpec(slug, executor, net, result_dir, timeout, body)`
  - `parse_taskfile(path) -> TaskSpec`（格式见 Task 1 README；缺字段/非法 executor/空 body 抛 ValueError）

- [ ] **Step 1: 写失败测试** `orchestra/broker/tests/test_taskfile.py`

```python
"""taskfile.py 单元测试。"""
import os
import tempfile
import unittest

import taskfile

SAMPLE = """# T-20260819-demo
executor: shell
net: optional
result: results/T-20260819-demo
timeout: 60
---
echo hello
"""

class TestParseTaskfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "T-20260819-demo.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_ok(self):
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(spec.slug, "T-20260819-demo")
        self.assertEqual(spec.executor, "shell")
        self.assertEqual(spec.net, "optional")
        self.assertEqual(spec.result_dir, "results/T-20260819-demo")
        self.assertEqual(spec.timeout, 60)
        self.assertEqual(spec.body, "echo hello")

    def test_default_timeout(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\necho hi\n")
        self.assertEqual(taskfile.parse_taskfile(self.path).timeout, 3600)

    def test_missing_field_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "---\necho hi\n")
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("缺少字段", str(cm.exception))

    def test_bad_executor_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: codex\n" "net: optional\n" "result: r\n" "---\nx\n")
        with self.assertRaises(ValueError):
            taskfile.parse_taskfile(self.path)

    def test_empty_body_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\n")
        with self.assertRaises(ValueError):
            taskfile.parse_taskfile(self.path)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_taskfile.py" -v 2>&1 | tail -3
```
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现** `orchestra/broker/taskfile.py`

```python
"""T-*.md 任务文件解析。严格格式：
头部为 key: value 行（# 开头为注释），`---` 单独一行后为执行体。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass
class TaskSpec:
    slug: str
    executor: str   # dsh | shell
    net: str        # required | optional
    result_dir: str
    timeout: int
    body: str

_REQUIRED = ("executor", "net", "result")

def parse_taskfile(path: str | Path) -> TaskSpec:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    header, sep, body = text.partition("\n---\n")
    if not sep:
        raise ValueError(f"{p}: 缺少 '---' 分隔行")
    fields: dict[str, str] = {}
    for line in header.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{p}: 头部行不是 key: value 格式: {line!r}")
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    missing = [k for k in _REQUIRED if k not in fields]
    if missing:
        raise ValueError(f"{p}: 缺少字段 {missing}")
    if fields["executor"] not in ("dsh", "shell"):
        raise ValueError(f"{p}: executor 必须为 dsh|shell，实际 {fields['executor']!r}")
    if fields["net"] not in ("required", "optional"):
        raise ValueError(f"{p}: net 必须为 required|optional")
    body = body.strip()
    if not body:
        raise ValueError(f"{p}: 执行体为空")
    return TaskSpec(
        slug=p.stem,
        executor=fields["executor"],
        net=fields["net"],
        result_dir=fields["result"],
        timeout=int(fields.get("timeout", "3600")),
        body=body,
    )
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_taskfile.py" -v 2>&1 | tail -3
```
Expected: `OK`（5 tests passed）

- [ ] **Step 5: Commit**

```bash
cd /d/pythonProject && git add orchestra/broker/taskfile.py orchestra/broker/tests/ && git commit -m "feat: broker taskfile parser with tests"
```

### Task 8: broker/executor.py — dsh/shell 双执行器

**Files:**
- Create: `D:\pythonProject\orchestra\broker\executor.py`
- Test: `D:\pythonProject\orchestra\broker\tests\test_executor.py`

**Interfaces:**
- Consumes: `taskfile.TaskSpec`
- Produces:
  - `run_task(spec, tasks_dir, results_root, dsh_profile="headless") -> tuple[str, str|None]`（返回 `(status, error)`；产出写 `results_root/<spec.result_dir>/attempt-<n>/`：stdout.log、stderr.log、state.json）
  - `check_net(host="api.deepseek.com", port=443, timeout=3) -> bool`（required 任务断网门）

- [ ] **Step 1: 写失败测试** `orchestra/broker/tests/test_executor.py`

```python
"""executor.py 单元测试（shell 分支真跑，dsh 分支用 mock，避免依赖真实 dsh）。"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import executor
import taskfile

def make_spec(body, executor="shell", timeout=30):
    return taskfile.TaskSpec(
        slug="T-20260819-test", executor=executor, net="optional",
        result_dir="results/T-20260819-test", timeout=timeout, body=body,
    )

class TestShellExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shell_ok(self):
        spec = make_spec("echo broker-ok")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        outdir = os.path.join(self.results, "results/T-20260819-test", "attempt-1")
        self.assertIn("broker-ok", open(os.path.join(outdir, "stdout.log"), encoding="utf-8").read())
        state = json.load(open(os.path.join(outdir, "state.json"), encoding="utf-8"))
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["executor"], "shell")

    def test_shell_fail_exit_code(self):
        spec = make_spec("exit 3")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("exit code 3", error)

    def test_shell_timeout(self):
        spec = make_spec("sleep 30", timeout=1)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("timeout", error)

    def test_missing_executable(self):
        spec = make_spec("nonexistent-cmd-xyz")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("not found", error)

    def test_attempt_increments(self):
        spec = make_spec("echo ok")
        executor.run_task(spec, self.tasks, self.results)
        executor.run_task(spec, self.tasks, self.results)
        base = os.path.join(self.results, "results/T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-1")))
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-2")))

class TestDshExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("subprocess.run")
    def test_dsh_prompt_contains_output_dir(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
        spec = make_spec("分析数据", executor="dsh")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        args, kwargs = mock_run.call_args
        outdir = os.path.join(self.results, "results/T-20260819-test", "attempt-1")
        self.assertIn("dsh", args[0][0])
        self.assertIn(outdir, args[0][2])  # prompt 注入输出目录
        self.assertEqual(kwargs["cwd"], self.tasks)

class TestCheckNet(unittest.TestCase):
    @mock.patch("socket.create_connection")
    def test_net_ok(self, mock_conn):
        self.assertTrue(executor.check_net())

    @mock.patch("socket.create_connection", side_effect=OSError("down"))
    def test_net_down(self, mock_conn):
        self.assertFalse(executor.check_net())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_executor.py" -v 2>&1 | tail -3
```
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现** `orchestra/broker/executor.py`

```python
"""执行器：dsh headless 与 shell 双通道，产出落 attempt-N 目录（增量落盘）。"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from taskfile import TaskSpec

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def check_net(host: str = "api.deepseek.com", port: int = 443, timeout: int = 3) -> bool:
    """required 任务的断网门：TCP 连通即视为有网。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def run_task(spec: TaskSpec, tasks_dir: str, results_root: str,
             dsh_profile: str = "headless") -> tuple[str, str | None]:
    """执行一个 TaskSpec。返回 (status, error)；status ∈ done|failed。"""
    base = Path(results_root) / spec.result_dir
    attempt = 1
    while (base / f"attempt-{attempt}").exists():
        attempt += 1
    outdir = base / f"attempt-{attempt}"
    outdir.mkdir(parents=True, exist_ok=True)

    if spec.executor == "dsh":
        prompt = f"输出目录: {outdir}\n所有产出文件必须写入该目录。\n\n{spec.body}"
        cmd = ["dsh", "--profile", dsh_profile, prompt]
    elif os.name == "nt":
        cmd = ["cmd", "/c", spec.body]
    else:
        cmd = ["/bin/sh", "-c", spec.body]

    started = time.time()
    stdout, stderr, status, error = "", "", "done", None
    try:
        proc = subprocess.run(
            cmd, cwd=str(tasks_dir), capture_output=True, text=True,
            timeout=spec.timeout, encoding="utf-8", errors="replace",
        )
        stdout, stderr = proc.stdout or "", proc.stderr or ""
        if proc.returncode != 0:
            status, error = "failed", f"exit code {proc.returncode}"
    except subprocess.TimeoutExpired as e:
        stdout, stderr = e.stdout or "", e.stderr or ""
        status, error = "failed", f"timeout after {spec.timeout}s"
    except FileNotFoundError as e:
        status, error = "failed", f"executable not found: {e.filename}"

    (outdir / "stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
    (outdir / "stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
    state = {
        "slug": spec.slug, "executor": spec.executor, "attempt": attempt,
        "status": status, "error": error, "started_at": _now(),
        "elapsed_s": round(time.time() - started, 1),
    }
    (outdir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return status, error
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_executor.py" -v 2>&1 | tail -3
```
Expected: `OK`（8 tests passed）

- [ ] **Step 5: Commit**

```bash
cd /d/pythonProject && git add orchestra/broker/executor.py orchestra/broker/tests/ && git commit -m "feat: broker executor - dsh/shell dual channels with attempt dirs"
```

### Task 9: broker/dispatcher.py — 主循环 + 断网门 + 恢复

**Files:**
- Create: `D:\pythonProject\orchestra\broker\dispatcher.py`
- Create: `D:\pythonProject\orchestra\broker\config.example.json`
- Test: `D:\pythonProject\orchestra\broker\tests\test_dispatcher.py`

**Interfaces:**
- Consumes: `db.*`、`taskfile.parse_taskfile`、`executor.run_task|check_net`
- Produces:
  - `load_config(path) -> dict`（字段：tasks_dir/results_dir/db_path/poll_interval/max_attempts/dsh_profile/api_url/monitor_token）
  - `one_cycle(cfg, conn, run=None, check_net_fn=None) -> dict`（返回 `{"executed": [...], "skipped_net": [...]}`；`run`/`check_net_fn` 为可注入替身，供测试）
  - `report_status(cfg, conn) -> None`（api_url 为空则 no-op；POST `/api/orchestra` 带 X-Monitor-Token）
  - `main()`（加载 config.json → init_db → recover_running → 循环 one_cycle+report_status+睡眠；SIGTERM 优雅退出）

- [ ] **Step 1: 写失败测试** `orchestra/broker/tests/test_dispatcher.py`

```python
"""dispatcher.py 单元测试（注入 fake run/check_net，全流程临时目录）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

import db
import dispatcher

TASK_MD = """# T-20260819-a
executor: shell
net: optional
result: results/T-20260819-a
---
echo ok
"""

def write_task(tasks_dir, name, body=TASK_MD, executor="shell", net="optional"):
    md = body.replace("# T-20260819-a", f"# {name}").replace("executor: shell", f"executor: {executor}").replace("net: optional", f"net: {net}")
    with open(os.path.join(tasks_dir, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(md)

def make_cfg(tmp):
    return {
        "tasks_dir": os.path.join(tmp, "tasks"),
        "results_dir": os.path.join(tmp, "results"),
        "db_path": os.path.join(tmp, "broker.db"),
        "poll_interval": 1, "max_attempts": 2, "dsh_profile": "headless",
        "api_url": "", "monitor_token": "",
    }

class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for d in ("tasks", "results"):
            os.makedirs(os.path.join(self.tmp.name, d))
        self.cfg = make_cfg(self.tmp.name)
        self.conn = db.init_db(self.cfg["db_path"])

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_full_cycle_queued_to_done(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        fake_run = mock.Mock(return_value=("done", None))
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)
        self.assertEqual(r["executed"], ["T-20260819-a"])
        self.assertEqual(db.list_tasks(self.conn, "done")[0][0], "T-20260819-a")

    def test_failure_retry_then_final_failed(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        fake_run = mock.Mock(return_value=("failed", "boom"))
        dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)  # attempt 1
        dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)  # attempt 2
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][1], "failed")  # attempts=2 终态
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)
        self.assertEqual(r["executed"], [])  # 不再执行

    def test_required_task_skipped_when_offline(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a", net="required")
        fake_run = mock.Mock()
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: False)
        self.assertEqual(r["skipped_net"], ["T-20260819-a"])
        fake_run.assert_not_called()
        self.assertEqual(db.list_tasks(self.conn, "queued")[0][0], "T-20260819-a")

    def test_idempotent_register(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)
        self.assertEqual(len(db.list_tasks(self.conn)), 1)  # done 不重跑

    def test_recovery_marks_running_failed(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        db.register_task(self.conn, "T-20260819-a", "optional", "results/T-20260819-a")
        db.claim_task(self.conn, "T-20260819-a")
        n = db.recover_running(self.conn)  # 模拟重启恢复
        self.assertEqual(n, 1)
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        self.assertEqual(db.list_tasks(self.conn, "done")[0][0], "T-20260819-a")  # 重试成功

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_dispatcher.py" -v 2>&1 | tail -3
```
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现** `orchestra/broker/dispatcher.py`

```python
"""Orchestra Broker dispatcher：轮询任务文件 → 执行 → 状态入库 → 可选上报。"""
from __future__ import annotations

import json
import logging
import signal
import time
import urllib.request
from pathlib import Path

import db
import executor
import taskfile

log = logging.getLogger("dispatcher")

def load_config(path: str = "config.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def report_status(cfg: dict, conn) -> None:
    api = cfg.get("api_url")
    if not api:
        return
    queued = len(db.list_tasks(conn, "queued"))
    running = len(db.list_tasks(conn, "running"))
    payload = {
        "broker_health": "ok",
        "queue_len": queued + running,
        "active_tasks": running,
        "last_task": db.list_tasks(conn, "done")[-1][0] if db.list_tasks(conn, "done") else None,
    }
    req = urllib.request.Request(
        api.rstrip("/") + "/api/orchestra",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Monitor-Token": cfg.get("monitor_token", ""),
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # 上报失败不影响主循环
        log.warning("status report failed: %s", e)

def one_cycle(cfg: dict, conn, run=None, check_net_fn=None) -> dict:
    """单轮：注册新任务 → 重排队失败任务 → 执行 queued。run/check_net_fn 供测试注入。"""
    run = run or executor.run_task
    check_net_fn = check_net_fn or executor.check_net
    tasks_dir = Path(cfg["tasks_dir"])
    max_attempts = int(cfg.get("max_attempts", 2))

    specs: dict[str, taskfile.TaskSpec] = {}
    for f in sorted(tasks_dir.glob("T-*.md")):
        try:
            spec = taskfile.parse_taskfile(f)
        except ValueError as e:
            log.error("跳过非法任务文件: %s", e)
            continue
        specs[spec.slug] = spec
        db.register_task(conn, spec.slug, spec.net, spec.result_dir)

    db.requeue_failed(conn, max_attempts)

    executed, skipped_net = [], []
    for slug, _st, _a, net_req, _e in db.list_tasks(conn, "queued"):
        spec = specs.get(slug)
        if spec is None:
            db.finish_task(conn, slug, "failed", "task file missing")
            continue
        if net_req == "required" and not check_net_fn():
            skipped_net.append(slug)
            continue
        if not db.claim_task(conn, slug):
            continue
        status, error = run(spec, str(tasks_dir), cfg["results_dir"],
                            dsh_profile=cfg.get("dsh_profile", "headless"))
        db.finish_task(conn, slug, status, error)
        executed.append(slug)
        log.info("task %s -> %s (%s)", slug, status, error or "-")
    return {"executed": executed, "skipped_net": skipped_net}

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(0)))
    cfg = load_config()
    conn = db.init_db(cfg["db_path"])
    n = db.recover_running(conn)
    if n:
        log.info("recovered %d running task(s) -> failed", n)
    poll = float(cfg.get("poll_interval", 30))
    log.info("broker started (poll=%ss, db=%s)", poll, cfg["db_path"])
    while True:
        try:
            one_cycle(cfg, conn)
            report_status(cfg, conn)
        except Exception:
            log.exception("cycle error")
        time.sleep(poll)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 写 config.example.json**

```json
{
  "tasks_dir": "/mnt/broker/tasks",
  "results_dir": "/mnt/broker/results",
  "db_path": "/mnt/broker/db/broker.db",
  "poll_interval": 30,
  "max_attempts": 2,
  "dsh_profile": "headless",
  "api_url": "",
  "monitor_token": ""
}
```
（真实 `config.json` 在 Pi 部署时创建，含 api_url 指向核桃派 usage-monitor 与 monitor_token——subsystem-4 上线后填，v1 留空）

- [ ] **Step 5: 运行确认通过**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -p "test_dispatcher.py" -v 2>&1 | tail -3
```
Expected: `OK`（5 tests passed）

- [ ] **Step 6: 全量回归**

```bash
cd /d/pythonProject/orchestra/broker && python -m unittest discover -s tests -t . -v 2>&1 | tail -3
```
Expected: `OK`（18 tests passed：db 5 + taskfile 5 + executor 8 + dispatcher 5 中重合计入总数）

- [ ] **Step 7: Commit**

```bash
cd /d/pythonProject && git add orchestra/broker/ && git commit -m "feat: broker dispatcher - poll loop, net gate, recovery, status report"
```

### Task 10: systemd 部署到 4B（service + timer + 代码同步）

**Files:**
- Create: `D:\pythonProject\orchestra\broker\orchestra-broker.service`（仓库内，scp 到 Pi）
- Create: `D:\pythonProject\orchestra\broker\inject_daily.sh`（定时注入示例任务）
- Create: `D:\pythonProject\orchestra\broker\orchestra-timer.timer` + `orchestra-timer.service`
- Create: `D:\pythonProject\orchestra\scripts\deploy_broker.sh`（一键部署脚本）

**Interfaces:**
- Consumes: Task 9 的 dispatcher.py 与 config.example.json；Task 3 的 /mnt/broker 目录
- Produces: 4B 上常驻服务 `orchestra-broker.service`（开机自启）；每晚 23:30 注入示例任务；`deploy_broker.sh` 供后续升级复用

- [ ] **Step 1: 写 service 文件** `orchestra/broker/orchestra-broker.service`

```ini
[Unit]
Description=Orchestra Broker dispatcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/liuxfs/broker
ExecStart=/usr/bin/python3 /home/liuxfs/broker/dispatcher.py
StandardOutput=append:/mnt/broker/logs/broker.log
StandardError=append:/mnt/broker/logs/broker.log
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 写定时注入示例** `orchestra/broker/inject_daily.sh`

```bash
#!/usr/bin/env bash
# 示例：每晚注入 arXiv 抓取任务（required 任务断网时 Broker 会自动跳过排队）
set -euo pipefail
D="$(date +%Y%m%d)"
TASK="/mnt/broker/tasks/T-${D}-nightly-arxiv.md"
[ -f "$TASK" ] && exit 0
cat > "$TASK" << 'EOF'
# T-nightly-arxiv
executor: shell
net: required
result: results/T-nightly-arxiv
---
curl -s "https://export.arxiv.org/api/query?search_query=cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=10" -o arxiv.xml && echo done
EOF
echo "injected $TASK"
```

- [ ] **Step 3: 写 timer 与配套 service** `orchestra/broker/orchestra-timer.timer` + `orchestra-timer.service`

```ini
# orchestra-timer.timer
[Unit]
Description=Orchestra nightly task injection

[Timer]
OnCalendar=*-*-* 23:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# orchestra-timer.service
[Unit]
Description=Orchestra nightly task injection

[Service]
Type=oneshot
ExecStart=/bin/bash /home/liuxfs/broker/inject_daily.sh
```

- [ ] **Step 4: 写一键部署脚本** `orchestra/scripts/deploy_broker.sh`

```bash
#!/usr/bin/env bash
# 部署 broker 代码到 4B 并 (re)start systemd 服务
set -euo pipefail
SSH_HOST="${ORCHESTRA_SSH_HOST:?用法: ORCHESTRA_SSH_HOST=192.168.x.x bash deploy_broker.sh}"
SSH_USER="${ORCHESTRA_SSH_USER:-liuxfs}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ssh "$SSH_USER@$SSH_HOST" 'mkdir -p /home/liuxfs/broker'
scp -q "$ROOT"/broker/{db.py,taskfile.py,executor.py,dispatcher.py,__init__.py,inject_daily.sh} "$SSH_USER@$SSH_HOST:/home/liuxfs/broker/"
scp -q "$ROOT"/broker/orchestra-broker.service "$ROOT"/broker/orchestra-timer.timer "$ROOT"/broker/orchestra-timer.service "$SSH_USER@$SSH_HOST:/tmp/"

ssh "$SSH_USER@$SSH_HOST" bash -s << 'REMOTE'
set -euo pipefail
sudo mv /tmp/orchestra-broker.service /tmp/orchestra-timer.timer /tmp/orchestra-timer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orchestra-broker.service
sudo systemctl enable --now orchestra-timer.timer
sudo systemctl status orchestra-broker.service --no-pager | head -5
REMOTE
echo "部署完成"
```

- [ ] **Step 5: Pi 上创建真实 config.json（含权限）**

```bash
ssh liuxfs@<4B_IP> 'cp /home/liuxfs/broker/config.example.json /home/liuxfs/broker/config.json && \
  sed -i "s|\"api_url\": \"\"|\"api_url\": \"http://<核桃派IP>:5000\"|" /home/liuxfs/broker/config.json 2>/dev/null; \
  chmod 600 /home/liuxfs/broker/config.json; \
  python3 --version; cat /home/liuxfs/broker/config.json'
```
Expected: python3 版本 ≥3.9；config.json 内容正确（若暂不知道核桃派 IP，api_url 保持空字符串，subsystem-4 时再填）。

- [ ] **Step 6: 执行部署与验证**

```bash
cd /d/pythonProject && ORCHESTRA_SSH_HOST=<4B_IP> bash orchestra/scripts/deploy_broker.sh
ssh liuxfs@<4B_IP> 'systemctl is-active orchestra-broker && systemctl list-timers orchestra-timer.timer | tail -2 && tail -3 /mnt/broker/logs/broker.log'
```
Expected: `active`；timer 显示下次触发时间；broker.log 出现 `broker started` 行。

- [ ] **Step 7: 重启自启验证**

```bash
ssh liuxfs@<4B_IP> 'sudo reboot' && sleep 45 && ssh liuxfs@<4B_IP> 'systemctl is-active orchestra-broker && df -h /mnt/broker | tail -1'
```
Expected: `active`，SSD 挂载正常。

- [ ] **Step 8: Commit**

```bash
cd /d/pythonProject && git add orchestra/broker/orchestra-*.{service,timer} orchestra/broker/inject_daily.sh orchestra/scripts/deploy_broker.sh && git commit -m "feat: broker systemd units, nightly timer example, deploy script"
```

### Task 11: 端到端验收（总 spec §6.1 smoke test）

**Files:**
- Create: `D:\pythonProject\orchestra\tasks\T-YYYYMMDD-e2e-dsh.md`（验收任务，执行后归档）
- Create: `D:\pythonProject\orchestra\tasks\T-YYYYMMDD-e2e-offline.md`（脱机 shell 任务）

**Interfaces:**
- Consumes: Task 1-10 全部产出
- Produces: 验收记录写入 `orchestra/reports/2026-08-e2e-acceptance.md` 并 commit；DECISIONS.md 记录验收结论

- [ ] **Step 1: 编写 dsh 端到端任务**（日期用当天实际值）

```bash
D=$(date +%Y%m%d) && cat > /d/pythonProject/orchestra/tasks/T-${D}-e2e-dsh.md << EOF
# T-${D}-e2e-dsh
executor: dsh
net: required
result: results/T-${D}-e2e-dsh
---
使用 curl 从 arXiv API（export.arxiv.org）抓取 cs.CL 领域最近提交的 3 篇论文，把标题与摘要写入 output.json（JSON 数组，每项含 title 与 abstract 字段），并报告 output.json 的绝对路径。
EOF
```

- [ ] **Step 2: 推送并等待执行**

```bash
cd /d/pythonProject && ORCHESTRA_SSH_HOST=<4B_IP> bash orchestra/scripts/sync_push.sh && \
  sleep 120 && ORCHESTRA_SSH_HOST=<4B_IP> bash orchestra/scripts/sync_pull.sh && \
  ls orchestra/results/T-$(date +%Y%m%d)-e2e-dsh/attempt-1/
```
Expected: attempt-1 目录含 stdout.log、stderr.log、state.json；state.json 的 status 为 done（若 dsh 首跑超过 120s，再 sleep 120 重拉一次）。

- [ ] **Step 3: 验证产出与复查闭环**

```bash
cd /d/pythonProject/orchestra/results/T-$(date +%Y%m%d)-e2e-dsh && \
  python -c "import json; d=json.load(open('attempt-1/output.json' if __import__('os').path.exists('attempt-1/output.json') else 'output.json', encoding='utf-8')); assert len(d)==3 and all('title' in x and 'abstract' in x for x in d), d; print('产出合法: 3 篇论文')" && \
  cat attempt-1/state.json | python -c "import json,sys; s=json.load(sys.stdin); print('status:', s['status'], 'elapsed:', s['elapsed_s'], 's')"
```
Expected: `产出合法: 3 篇论文`；state.json status=done。（若 output.json 在 tasks 目录而非 attempt 目录，检查 stdout.log 中 dsh 报告的实际路径——v1 通过 prompt 注入输出目录，此处按注入约定应在 attempt-1 下；若不符，记录到验收报告并在 reports 中注明 dsh 实际行为，不修改 broker 代码）

- [ ] **Step 4: 脱机场景验证（Windows 关机 20 分钟）**

```bash
D=$(date +%Y%m%d) && cat > /d/pythonProject/orchestra/tasks/T-${D}-e2e-offline.md << EOF
# T-${D}-e2e-offline
executor: shell
net: optional
result: results/T-${D}-e2e-offline
---
for i in 1 2 3 4 5; do date +%s >> heartbeat.txt; sleep 240; done; echo done
EOF
cd /d/pythonProject && ORCHESTRA_SSH_HOST=<4B_IP> bash orchestra/scripts/sync_push.sh
```
推送后**关闭 Windows 主机**（用户操作，约 20 分钟），期间 Broker 在 4B 上持续执行。重新开机后：

```bash
cd /d/pythonProject && ORCHESTRA_SSH_HOST=<4B_IP> bash orchestra/scripts/sync_pull.sh && \
  wc -l < orchestra/results/T-$(date +%Y%m%d)-e2e-offline/attempt-1/heartbeat.txt
```
Expected: `5`——5 个心跳时间戳全部在 Windows 关机期间写入，证明脱机不中断。

- [ ] **Step 5: 中断恢复验证**

```bash
ssh liuxfs@<4B_IP> 'sudo systemctl stop orchestra-broker && sleep 2 && sudo systemctl start orchestra-broker && sleep 5 && tail -5 /mnt/broker/logs/broker.log && sqlite3 /mnt/broker/db/broker.db "SELECT slug,status,attempts,error FROM tasks;" 2>/dev/null || python3 -c "import sqlite3; print(sqlite3.connect(\"/mnt/broker/db/broker.db\").execute(\"SELECT slug,status,attempts,error FROM tasks\").fetchall())"'
```
Expected: 若停机时有 running 任务 → 日志出现 `recovered N running task(s) -> failed`，且该任务随后被重试（attempts≥1）至 done/failed 终态。

- [ ] **Step 6: 写验收报告并归档**

```bash
cat > /d/pythonProject/orchestra/reports/2026-08-e2e-acceptance.md << 'EOF'
# Subsystem 1 端到端验收报告

- dsh 任务全闭环（派→执行→复查）：通过/未通过（附 state.json 摘要）
- Windows 脱机 20 分钟 shell 任务照跑：heartbeat 行数 = ___
- 中断恢复（recover→重试）：通过/未通过
- dsh 实际产出路径行为：按 prompt 注入 / 偏离（记录实际位置）
- 遗留问题：___
EOF
```
填写实际结果后 commit：

```bash
cd /d/pythonProject && git add orchestra/reports/ && git commit -m "docs: subsystem-1 e2e acceptance report"
```

---

## Self-Review 记录

- **Spec 覆盖**：§6.1 的队列持久化（Task 6）、任务注入（Task 1+11）、dispatcher（Task 9）、checkpoint/attempt 增量落盘（Task 8）、停机恢复（Task 9 recover_running + Task 11 Step 5）、systemd timer（Task 10）、dsh 安装与 Minimal→Standard 演进（Task 5 决策门；Standard 评估为 GO 后事项，已记录）、冒烟验收（Task 11）、降级链 Windows 本地 dsh（Task 2）。§5 任务文件模板字段（executor/priority/schedule/net/prompt/acceptance）中 priority/schedule/acceptance 三字段 v1 未实现——**明确取舍**：priority 在队列规模为个位数时无意义（YAGNI）、schedule 由 systemd timer 承担、acceptance 由 CC 复查承担（reports/）；已在 Task 1 README 的严格格式中移除这三字段，与总 spec 的偏差记录于 DECISIONS 021。
- **占位符扫描**：无 TBD/TODO；`<4B_IP>`/`<核桃派IP>` 为部署期环境变量（Task 3 首步含发现 IP 的明确操作），非代码占位。
- **类型一致性**：`TaskSpec` 字段在 Task 7 定义、Task 8/9 消费一致；`run_task(spec, tasks_dir, results_root, dsh_profile)` 签名在 Task 8 定义、Task 9 注入点一致；db 函数签名 Task 6 定义、Task 9 调用一致。
