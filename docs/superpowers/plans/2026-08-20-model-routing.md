# 统一模型路由表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地一张用户维护、系统只读的模型路由表（`orchestra/config/model-routing.json`），dsh 侧按任务卡 `model:` 字段切 flash/pro（--patch 机制），codex 侧 CC 查表传 --model（零代码）。

**Architecture:** 写卡时填死——CC 写任务卡时查表把 `model:` 写进卡头；broker 解析后由 executor 映射为 dsh `--patch` 覆盖层。Pi 侧不知道表的存在。spec：`docs/superpowers/specs/2026-08-20-model-routing-design.md`。

**Tech Stack:** Python 3.11 stdlib（broker）、dsh 0.1.0-rc.7（--patch 覆盖层）、JSON 路由表、unittest、Git Bash。

## Global Constraints

- commit 不加 Co-Authored-By/任何署名行
- broker 41 单测基线零回归（改动后 ≥43）
- stdlib only，不装任何 pip 包
- **Plus 未购买前：codex 侧零真实调用**（消费链 B 无代码，本计划不含 codex 实测）
- 证据/临时文件放 `D:\Temp\subsystem-5\`
- Pi 部署（Task 5）需用户配合部署窗口；4B 上 broker 以 liuxfs 运行

---

### Task 0: dsh patch 结构调研 + flash/pro patch 文件

**Files:**
- Create: `D:\pythonProject\orchestra\dsh-patches\flash.yml`
- Create: `D:\pythonProject\orchestra\dsh-patches\pro.yml`

**Interfaces:**
- Consumes: dsh 0.1.0-rc.7（Windows 已装）
- Produces: 两枚 patch yml（供 Task 3 的 executor 引用路径 /mnt/broker/dsh-patches/{model}.yml 与 Task 5 部署）

- [ ] **Step 1: 导出 headless profile 配置树**

Run: `dsh --profile headless --dump-config > D:\Temp\subsystem-5\dsh-config.txt 2>&1`
Read `D:\Temp\subsystem-5\dsh-config.txt`，定位 provider/model 相关段（模型名字段长什么样、在哪一层）。若该命令失败或输出不含 provider 段，改跑 `dsh --dump-default-config`；两者都没有则 STATUS: BLOCKED。

- [ ] **Step 2: 写 flash.yml**（以 Step 1 观察到的结构为准，只覆盖模型字段；若结构如 `provider: {model: xxx}` 层级则对应嵌套）：

```yaml
# dsh patch overlay：雷达评分等省钱型任务
provider:
  model: deepseek-v4-flash
```

（模型名以 dump-config 里现有 provider 段命名风格为准；若显示的是别的命名体系，按实际命名体系改写并记录。）

- [ ] **Step 3: 写 pro.yml**

```yaml
# dsh patch overlay：实验跑批等质量型任务
provider:
  model: deepseek-v4-pro
```

- [ ] **Step 4: 验证 patch 生效**

Run: `dsh --profile headless --patch D:\pythonProject\orchestra\dsh-patches\flash.yml --dump-config > D:\Temp\subsystem-5\dsh-flash-config.txt 2>&1`
确认输出中模型字段已变为 flash 对应值（与 Step 1 的默认值不同）。pro.yml 同法验证。

- [ ] **Step 5: Commit**

```bash
git add orchestra/dsh-patches/flash.yml orchestra/dsh-patches/pro.yml
git commit -m "feat: dsh model patches - flash/pro overlays for routing table"
```

---

### Task 1: 路由表落盘

**Files:**
- Create: `D:\pythonProject\orchestra\config\model-routing.json`

**Interfaces:**
- Produces: 路由表文件（CC 读表用；本计划代码侧不读它——消费链 B 零代码约定）

- [ ] **Step 1: 写文件**（内容逐字 = spec §3 定稿）：

```json
{
  "dsh": { "radar-scoring": "flash", "experiment": "pro" },
  "codex": {
    "default": "terra",
    "batch-summarize": "luna",
    "radar-summary": "luna",
    "vision-quick": "luna",
    "mutual-review": "terra",
    "claim-check": "terra",
    "docs-draft": "terra",
    "dual-implement": "terra",
    "complex-audit": { "model": "sol", "effort": "high" },
    "production-fix": { "owner": "claude" }
  }
}
```

- [ ] **Step 2: 验证 JSON 合法**

Run: `python -c "import json; json.load(open('orchestra/config/model-routing.json', encoding='utf-8')); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add orchestra/config/model-routing.json
git commit -m "feat: model-routing.json - user-maintained model policy table (spec 2026-08-20)"
```

---

### Task 2: taskfile.py — TaskSpec.model 字段（TDD）

**Files:**
- Modify: `D:\pythonProject\orchestra\broker\taskfile.py`
- Test: `D:\pythonProject\orchestra\broker\tests\test_taskfile.py`

**Interfaces:**
- Consumes: 既有 `TaskSpec` dataclass 与 `parse_taskfile(path)`（测试文件已 Read 过，沿用其 tempfile 模式）
- Produces: `TaskSpec.model: Optional[str]`（None=缺省；值透传不校验）

- [ ] **Step 1: 写失败测试**（追加到 test_taskfile.py；如既有 helper 模式不同按既有为准）：

```python
def test_model_field_optional_default_none(self):
    spec = self._parse("")   # 复用既有 helper；无则按既有模式用 tempfile 写卡
    self.assertIsNone(spec.model)

def test_model_field_passthrough(self):
    self.assertEqual(self._parse("model: flash\n").model, "flash")
    self.assertEqual(self._parse("model: pro\n").model, "pro")

def test_model_field_not_validated(self):
    # 档位校验责任在写卡的 CC；解析层透传
    self.assertEqual(self._parse("model: weird-tier\n").model, "weird-tier")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd orchestra/broker && python -m unittest tests.test_taskfile -v`
Expected: FAIL（AttributeError: 'TaskSpec' object has no attribute 'model' / 断言失败）

- [ ] **Step 3: 实现**

taskfile.py 两处改动：
```python
@dataclass
class TaskSpec:
    slug: str
    executor: str   # dsh | shell
    net: str        # required | optional
    result_dir: str
    timeout: int
    body: str
    model: str | None = None   # dsh 模型档位（flash|pro），缺省用 profile 默认
```
parse_taskfile 返回处加：
```python
        model=fields.get("model"),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd orchestra/broker && python -m unittest tests.test_taskfile -v`
Expected: PASS；随后 `python -m unittest discover -s tests` 应 Ran 44 OK（41 + 3 新）

- [ ] **Step 5: Commit**

```bash
git add orchestra/broker/taskfile.py orchestra/broker/tests/test_taskfile.py
git commit -m "feat: taskfile - parse optional model field for dsh routing"
```

---

### Task 3: executor.py — model → --patch 映射（TDD）

**Files:**
- Modify: `D:\pythonProject\orchestra\broker\executor.py`
- Test: `D:\pythonProject\orchestra\broker\tests\test_executor.py`

**Interfaces:**
- Consumes: `run_task(spec, tasks_dir, results_root, dsh_profile="headless")`、TaskSpec.model（Task 2）、patch 路径约定 `/mnt/broker/dsh-patches/{model}.yml`
- Produces: dsh 任务带 model 时 argv 追加 `--patch <path>`；patch 文件缺失 → status="failed" + error 含 `model patch not found`（state.json 照常落盘）

- [ ] **Step 1: 写失败测试**（追加到 test_executor.py，沿用既有 Popen mock 模式）：

```python
@mock.patch("os.path.exists", return_value=True)
@mock.patch("subprocess.Popen")
def test_dsh_model_appends_patch(self, popen, _exists):
    proc = popen.return_value
    proc.communicate.return_value = ("", "")
    proc.returncode = 0
    spec = self._make_spec(model="flash")   # 复用/新建 helper 构造 TaskSpec
    with tempfile.TemporaryDirectory() as d:
        status, _ = run_task(spec, d, d)
    argv = popen.call_args.args[0]
    self.assertIn("--patch", argv)
    self.assertEqual(argv[argv.index("--patch") + 1], "/mnt/broker/dsh-patches/flash.yml")
    self.assertEqual(status, "done")

@mock.patch("os.path.exists", return_value=False)
@mock.patch("subprocess.Popen")
def test_dsh_model_missing_patch_fails(self, popen, _exists):
    spec = self._make_spec(model="pro")
    with tempfile.TemporaryDirectory() as d:
        status, error = run_task(spec, d, d)
    self.assertEqual(status, "failed")
    self.assertIn("model patch not found", error)
    popen.assert_not_called()
    # state.json 仍落盘
    self.assertTrue(any(Path(d).rglob("state.json")))

@mock.patch("os.path.exists", return_value=True)
@mock.patch("subprocess.Popen")
def test_dsh_no_model_no_patch(self, popen, _exists):
    proc = popen.return_value
    proc.communicate.return_value = ("", "")
    proc.returncode = 0
    with tempfile.TemporaryDirectory() as d:
        run_task(self._make_spec(model=None), d, d)
    self.assertNotIn("--patch", popen.call_args.args[0])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd orchestra/broker && python -m unittest tests.test_executor -v`
Expected: FAIL（--patch 断言失败 / model patch not found 断言失败）

- [ ] **Step 3: 实现**（executor.py dsh 分支改造 + Popen 守卫）：

现状（约 36-42 行）：
```python
    if spec.executor == "dsh":
        prompt = f"工作目录: {outdir}\n所有产出文件必须写入该目录。\n\n{spec.body}"
        cmd = ["dsh", "--profile", dsh_profile, prompt]
```
改为：
```python
    if spec.executor == "dsh":
        prompt = f"工作目录: {outdir}\n所有产出文件必须写入该目录。\n\n{spec.body}"
        cmd = ["dsh", "--profile", dsh_profile]
        if spec.model:
            patch_path = f"/mnt/broker/dsh-patches/{spec.model}.yml"
            if not os.path.exists(patch_path):
                status, error = "failed", f"model patch not found: {patch_path}"
            else:
                cmd += ["--patch", patch_path]
        if status == "done":
            cmd.append(prompt)
```
Popen 块（现状 `try: proc = subprocess.Popen(...)` 起）加守卫：
```python
    if status == "done":
        try:
            proc = subprocess.Popen(...)   # 原块整体缩进一层
```
（保持原有 try/except 分支与 killpg/超时逻辑不变；缩进层级对应调整。state.json/stdout.log 写入行在 try 块外不动。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd orchestra/broker && python -m unittest tests.test_executor -v && python -m unittest discover -s tests`
Expected: 新测试 PASS；全量 Ran 46 OK（41 + Task 2 的 3 + 本任务 3，若 helper 复用减少则对应调整，以实际计数为准且必须 ≥ 43）

- [ ] **Step 5: Commit**

```bash
git add orchestra/broker/executor.py orchestra/broker/tests/test_executor.py
git commit -m "feat: executor - map task model field to dsh --patch overlay"
```

---

### Task 4: 文档同步

**Files:**
- Modify: `D:\pythonProject\docs\superpowers\specs\2026-08-18-research-orchestra-design.md`（§8 策略表路径、§5 任务模板纪律）
- Modify: `D:\pythonProject\CLAUDE.md`（挂账更新）
- Modify: `D:\pythonProject\orchestra\README.md`（补路由表小节）

**Interfaces:**
- Consumes: 本计划 Task 0-3 的产物路径与约定
- Produces: 文档与实现一致（哨兵 Task 6 核对的锚点）

- [ ] **Step 1: 总 spec §8 更新**：Read §8 原文，把「策略表位于 `orchestra/config/model-routing.md`」改为「策略表位于 `orchestra/config/model-routing.json`（用户维护、系统只读；值为抽象档位键，具体模型名在执行侧）」

- [ ] **Step 2: 总 spec §5 加纪律句**：任务模板节末尾加一行：「长实验任务卡 `timeout` 必须显式设置（防长任务堵塞队列挤占夜间雷达）」

- [ ] **Step 3: CLAUDE.md 挂账更新**：把「双 agent 能力拓展想法池待选」条改为「模型路由表已定稿落地（spec 2026-08-20）；双 agent 想法池剩余项（resume 脚本化/usage 统计）待选」

- [ ] **Step 4: orchestra/README.md 补节**：在双 agent 节后加「## 模型路由表」小节：表路径、写卡时填死约定（任务卡 `model: flash|pro`）、codex 三档映射一句话、patch 文件位置

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-18-research-orchestra-design.md CLAUDE.md orchestra/README.md
git commit -m "docs: sync spec/README/CLAUDE.md with model routing table"
```

---

### Task 5: Pi 部署 + flash 真实冒烟（需用户配合部署窗口）

**Files:** 无仓库改动（部署 + 证据）

**Interfaces:**
- Consumes: Task 0-4 产物；4B 现有 deploy 通道（`orchestra/scripts/deploy_broker.py` 与 sync_push.sh）
- Produces: 4B `/mnt/broker/dsh-patches/{flash,pro}.yml` + 新版 taskfile.py/executor.py 在役；冒烟证据 `D:\Temp\subsystem-5\`

- [ ] **Step 1: 部署 patch 文件**：scp `orchestra/dsh-patches/*.yml` → 4B `/mnt/broker/dsh-patches/`（mkdir 先建）
- [ ] **Step 2: 部署 broker 代码**：走 `deploy_broker.py`（或与 026 相同的 scp 路径）更新 taskfile.py/executor.py；`systemctl restart broker` 后 `systemctl status` 确认 active；md5 与本地 HEAD blob 一致
- [ ] **Step 3: flash 冒烟任务卡**：写最小雷达评分卡（`# T-model-smoke`，`executor: dsh`，`model: flash`，评分 3 篇样例论文），sync_push 入队
- [ ] **Step 4: 验证**：attempt 落盘、state.json status=done、dsh 日志/ps 显示进程带 `--patch /mnt/broker/dsh-patches/flash.yml`；证据截图/文本存 `D:\Temp\subsystem-5\`
- [ ] **Step 5: 收尾**：冒烟任务卡归档；证据清单写入 mission BRIEF

---

### Task 6: 哨兵审计 + 归档（mission 029 终审，8 维度同 026/027 模板）

（执行时按 sustained-development 流程：终审 AC → 处置 → 归档 completed/029_…）

---

## Self-Review 记录

- **Spec 覆盖**：§3 表（Task 1）、§4 链路 A 全部改动（Task 0/2/3/5）、spec §8 同步与 §5 纪律（Task 4）、§5 消费链 B 零代码（本计划无对应任务——约定项，Plus 购买后另列开放项，已注明）、§7 out of scope 无任务 ✓
- **占位符扫描**：Task 0 的 yml 内容以 dump-config 实测结构为准（研究型任务，非代码占位）；其余步骤均含完整代码/命令 ✓
- **类型一致性**：`TaskSpec.model`（Task 2 定义 `model: str | None = None`）↔ Task 3 测试/实现 `spec.model` ✓；patch 路径 `/mnt/broker/dsh-patches/{model}.yml` 三处一致 ✓
- **风险预案**：Task 0 dump-config 结构不符预期 → 以实际结构改写 yml 并如实记录；Task 3 缩进改造若牵连 killpg 逻辑 → 保持 try 块原逻辑仅加外层守卫；Pi 部署窗口未到 → Task 5 挂起不阻塞前 4 任务提交
