# Bogda runner 工作交接 — 2026-09-10

用户因额度不足要求停在交接点。当前没有继续部署或下载任务；常驻 worker 正常运行。下一会话先读本文和 `.tasks/active/059_bogda-campus-runner/STATE.md`，不要重新初始化机器。

## 已验证的现网

| 项目 | 结果 |
|---|---|
| 管理机 | laptop-w0cessade，100.103.79.3，工作区 D:/pythonProject |
| RK3528 | 100.78.158.80，SSH liuxfs；Prefect 4200、3101、Samba、NAS 备份和 Prefect 快照在线 |
| runner | DESKTOP-J3KNU65，100.73.48.81，SSH 19041；Y7000 2021H、i5-11400H、16GB、Win10 Home 19045 |
| 存储 | C 512GB、D 128GB；E 为外接 ORICO 盘，原 VPN 在该盘，移动时断开曾导致联网故障 |
| SSH | Program Files/OpenSSH 10，Automatic；公钥登录通过。防火墙 SSH 来源仅管理机 IP |
| Linux | WSL 2.7.13，Ubuntu 24.04.4，发行版 BogdaRunner，C:/WSL/BogdaRunner，默认用户 bogda |
| 依赖 | Python 3.11.16、uv 0.12.12、Prefect 3.8.3；离线 locked uv 启动通过 |
| NAS | //100.78.158.80/nas → /mnt/nas；WSL 与 RK bogda 用户双向读写通过 |
| worker | dorm-x86 / runner queue；worker、pool、queue、deployment 并发均为 1 |
| 自动启动 | Windows 登录后任务 BogdaRunnerWSL 保持 WSL 运行；Linux systemd 管理 worker |
| 恢复测试 | 终止并重新启动 WSL 后，NAS 和 worker 自动恢复；初始化约 80 秒。整机再次重启尚未复测 |
| 控制台 | http://rk3528.tail6d8b09.ts.net:3101/ ，仍为 real-readonly / observer；基础设施页已显示 dorm-x86 READY、worker ONLINE |
| Orchestra | broker、雷达、exam-watch、旧冷备、housekeeping 已停并禁用；管理机旧刷新任务禁用、3100 无监听；历史数据保留 |

## 精确资源和验收结果

- pool：`def7d303-c811-4024-9505-67e1b0917bd1`，名称 `dorm-x86`。
- queue：`2e773bf9-cba7-46ed-b93d-f1b2ea65dc27`，名称 `runner`。
- flow：`e6a7b6b1-7427-4431-a9ea-003302b30861`，名称 `bogda-shell-job`。
- deployment：`ebd2b9ce-46e3-4db2-9ad3-1a6e39b5fd02`，名称 `runner-shell-smoke`。
- 自主 smoke：`b70b2af8-e9dc-46a3-831a-c4ae3bb83095`，Completed；stdout 和 smoke.txt 均为 runner smoke ok，stderr 为空。
- supervised 验收：`66d4a924-4275-47ba-81db-4805964aa913`，Failed；尚未实际进入暂停。原因是 checkpoint Artifact key 中 kind 含下划线，被 Prefect 模型拒绝。
- 没有调用付费模型，也没有派发真实科研任务。

## 本地修复与部署边界

checkpoint key 修复已在管理机工作区完成、尚未部署到 runner 或 RK：

- `bogda/src/bogda/flows/research_checkpoint.py`：kind.value 中的下划线转为连字符。
- `bogda-console/src/bogda_console/adapters/prefect_api.py`：使用相同 key 规则，console 保持独立包契约。
- `bogda/tests/flows/test_research_checkpoint.py`：真实 Prefect Artifact 模型覆盖全部 CheckpointKind。
- `bogda-console/tests/backend/test_prefect_adapter_contract.py`：查询 key 格式回归。

子 agent 已完成红测、修复和两个对应测试文件绿测；协调者复跑 core checkpoint 测试通过，并审阅实际代码差异。未 commit、未 push。先前 runner 启动路径与 handshake ID 查询修复已在 runner 安装包中，针对性验证通过。

## 接班后的顺序

1. 确认 SSH、dorm-x86 heartbeat 和目标部署无活动任务。保留常驻 worker，不重复安装 WSL/Python，也不要重跑资源创建脚本。
2. 审阅上述四个本地修改；将 core checkpoint 修复送到 runner 当前源码，把 console adapter 修复送到 RK 的实际模块路径。部署前读取实际路径并保存旧文件；不要整仓覆盖。
3. RK console 使用 `/opt/bogda-console/.venv/bin/python`，WorkingDirectory=/opt/bogda-console，systemd 额外设置 `PYTHONPATH=/opt/bogda/src`。单独启动该 venv Python 没有这个变量时 import bogda 会失败。
4. 使用 D:/Temp/.codex-session/accept-runner-checkpoints.py 重测前，把其中 idempotency_key 改为新的 v2 值；否则会返回上述已失败的同一 run。使用现有 deployment ID，验证 experiment_approval、scientific_review 两次真实 Paused→恢复→Completed。
5. 核对 3101 的 checkpoint 展示和精确白名单后再开放对应操作。当前 profile、role、空白名单均未改变；不要将本地绿测记为 DEF-03 现网通过。
6. 处理下面的软件接线缺口，再判断是否达到完整接替验收。

## 尚未完成的软件接线

- 审批和 usage-unknown SQLite 当前硬编码 WAL。跨主机 CIFS 不能直接复用 WAL；仅改 DELETE 也不能直接证明跨主机事务可靠。倾向让 RK 单机持有库，runner 经窄接口访问；此方案尚未实施。
- worker runtime 尚未实际按共享环境变量构造审批/recovery store；环境文件存在不等于接线完成。
- shell 日志在本地 `attempts_root/job_id/run_id/attempt-0001/`；SafeLogReader 期望 `artifact_root/run_id/attempt-*/`。自动发布/归档尚未接通，3101 artifact root 尚未配置。
- 一次性付费审批、真实 usage-unknown 恢复、控制台日志联动未验收。保留只读状态。
- 宿舍与实验室跨网络实测、Windows 再次整机重启恢复尚未完成。

## 文件与凭据位置

- runner 源码 `/home/bogda/research-orchestra/bogda`；工作目录 `/home/bogda/bogda-work`，均在 WSL ext4。
- runner `/home/bogda/.config/bogda/runner.env` 和 `nas.cred`；凭据 mode 600。不要打印内容。
- RK `/etc/bogda/runner.env` 保存本次 Prefect auth 和新 HMAC；该配置已通过 SSH 内存转传到 runner，HMAC 尚未接入 console。
- runner `/etc/fstab` 配置 `noauto,_netdev,x-systemd.automount,x-systemd.mount-timeout=30s`；noauto 避免 WSL mount -a 与 systemd 重复挂载。
- runner `/etc/systemd/system/bogda-runner-worker.service`，启用并运行；Windows `BogdaRunnerWSL` 为登录触发隐藏任务，需要用户登录 Windows。
- NAS `/mnt/nas/.bogda/runner/artifacts/onboarding-20260910.txt` 是双向读写证据。误生成的同名 CR 后缀文件保留，未经用户同意不要清理。
- 管理机临时目录 `D:/Temp/.codex-session/bogda-onboarding-20260910` 保存安装包和验收脚本；runner 临时目录 `D:/Temp/.codex-session`。另有未完成的备用 Python 压缩包，不能当作完整安装包使用。
- SSH 原服务配置备份在 runner `D:/Temp/.codex-session/sshd-before-path-fix.json`；初始 fstab 备份 `fstab-before-bogda`。RK 原共享目录 ACL 备份 `/tmp/bogda-onboarding-20260910/pre-runner.acl`。

## 操作约束和节约额度

用户要求：不删除文件、不输出凭据、不改变模型路由，不接 Wake Bridge，不把研究任务投到 pi-service；保留既有未提交的学术技能改动。独立小任务可用低成本模型，协调者负责集成。没有待等的安装进程；旧 exec ID 不应继续轮询。

下载教训：直接 PyPI 很慢；本次由 uv.lock 导出带哈希 requirements，通过 TUNA 安装，再安装本地 editable 包。uv.lock 与管理机 SHA256 一致，版本未更新。不要再次全量下载或重新建 venv。

续接提示：读取本交接和 STATE，从“部署已验证的 checkpoint key 修复并重测”继续；先核对现网，再操作，不从头安装。

## 2026-09-10 续接结果（交接后同班执行）

交接顺序 1–5 已执行完毕：

- 现网核对：SSH 双机通；dorm-x86 READY（heartbeat）；目标 deployment 无活动 run；worker active。
- 部署：core 修复 → runner 源码，console adapter 修复 → RK `/opt/bogda-console/src/bogda_console/adapters/prefect_api.py`，均备份旧文件（`*.pre-keyfix-20260910`、`*.pre-keyfix2-20260910`）、py_compile 通过；console 服务重启后 active。
- **第二次失败暴露第二处缺陷**：v2 run `cff1fc6b-e3da-49fc-b6eb-f95502ffafff` 在 artifact key 修复生效后，pause key `paused-experiment_approval-…-schema` 被 FlowRunInput 校验拒绝。根因同为 kind（StrEnum 值含下划线）直接进入服务端 key；以 `_kind_slug` 归一化，decision_key 与 pause key 共用；新增回归测试用真实 FlowRunInput 模型覆盖全部 CheckpointKind（checkpoint 12、flows 35、console 契约 7 全绿）。
- **v3 验收通过**：run `11505d2b-dbe3-4b83-9488-070d7ae38c20`，experiment_approval、scientific_review 两次真实 Paused→恢复→Completed；服务端独立复核 Completed，artifact key 全部归一化，run-result 落盘。
- 3101：已显示该 run（COMPLETED，real/fresh）；checkpoint 展示经 v2 待决 artifact 验证（kind/commandVersion/impact 正确组装）。白名单核对：`real-readonly`/`observer`、四个 ALLOWED 名单仍为空，未开放任何写操作；**DEF-03 仍未通过现网验收**。未 commit/push，未调用付费模型。

剩余未变（接线缺口，见“尚未完成的软件接线”）：审批/usage SQLite 跨主机 WAL、worker store 按共享 env 构造、shell 日志自动发布到 3101 artifact root、一次性付费审批与真实 usage-unknown 恢复、宿舍–实验室跨网络实测、Windows 整机重启复测。**完整接替验收仍未达到**；下一步先由 owner 拍板审批/usage 库的部署形态（RK 单机持库 + runner 窄接口，或替代方案）。
