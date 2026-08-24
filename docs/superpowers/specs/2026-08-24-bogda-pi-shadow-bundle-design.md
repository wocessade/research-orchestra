# Bogda Pi 影子部署包设计

> 日期：2026-08-24
>
> 状态：已批准，待实施
>
> 范围：只制作和本地验证部署包，不连接或修改 Pi

## 1. 目标

本阶段为 Bogda 阶段 1 准备一个仓库原生、可审查、可 dry-run、可回滚的 Pi 部署包。它定义未来如何在树莓派 4B 2GB 上运行 Prefect Server 3.8.3、单并发 `pi-service` Worker、SQLite 一致性快照和 72 小时健康采样，但本阶段不通过 SSH 连接 Pi，不安装服务，也不接管 Orchestra 的真实任务。

部署包解决的是“未来部署能否重复、验证和撤回”，不是“现在立即上线”。真机安装与 72 小时验收必须在独立部署窗口中再次获得授权。

## 2. 方案选择

### 2.1 采用：仓库原生部署包

部署包由现有 Python 运行时、少量 POSIX shell、systemd unit 模板、机器可读 manifest、测试和运行手册组成。它不引入新的常驻控制面，也不创建第二套任务状态。

选择理由：

- 一台 Pi 不值得引入 Ansible inventory、role 和额外控制依赖；
- 纯手工运行手册无法持续证明路径、秘密、快照和回滚契约；
- Python 标准库足以完成 SQLite 一致性快照、恢复验证和健康采样；
- shell 只负责 Linux 主机上的安装边界，业务逻辑保持在可测试的 Python 单元中。

### 2.2 不采用：Ansible role

Ansible 的幂等和远程执行能力适合多节点，但当前只有一台 Pi，且本阶段明确不远程部署。它会增加 inventory、连接凭据和额外调试面，收益不足。

### 2.3 不采用：纯手工运行手册

纯手册初始成本最低，但容易让服务文件、权限、数据根和回滚步骤随时间漂移，不能为后续 72 小时验收提供可信基线。

## 3. 范围边界

本阶段实现：

- Prefect Server 和 `pi-service` Worker 的 systemd unit 模板；
- 无秘密的环境变量示例和部署 manifest；
- 安装前检查、dry-run、安装和回滚 shell 入口；
- SQLite 一致性快照、恢复验证和最小保留策略；
- 72 小时影子运行所需的健康采样与汇总证据；
- 未来真机部署、回滚和验收运行手册；
- Windows 上的 Python 测试与 Git Bash shell 语法检查。

本阶段不实现：

- 任何 SSH、scp、远程写入或服务重启；
- Wake Bridge、WoL、直连网口或宿舍机在线判断；
- 当前笔记本或宿舍机 Worker；
- Windows Power Agent、游戏模式和睡眠抑制；
- 雷达、通知、备份等现有任务迁移；
- 真实科研任务、Docker、CUDA 或 GPU；
- 3100 控制台和 `bogda-console` 合并；
- SLC/pSLC SD 卡采购或并发扩展。

## 4. 目录与职责

```text
bogda/
├── deploy/pi/
│   ├── manifest.toml
│   ├── bogda.env.example
│   ├── install.sh
│   ├── rollback.sh
│   └── systemd/
│       ├── bogda-prefect-server.service
│       ├── bogda-pi-worker.service
│       ├── bogda-prefect-snapshot.service
│       ├── bogda-prefect-snapshot.timer
│       ├── bogda-shadow-health.service
│       └── bogda-shadow-health.timer
├── src/bogda/ops/
│   ├── __init__.py
│   ├── bundle.py
│   ├── snapshot.py
│   └── health.py
├── tests/ops/
│   ├── test_bundle.py
│   ├── test_snapshot.py
│   └── test_health.py
└── docs/pi-shadow-runbook.md
```

`bundle.py` 读取固定 manifest 并执行本地检查或生成 staging 预览；它不执行远程命令。`snapshot.py` 只负责 SQLite backup API、SHA-256 manifest 和恢复验证。`health.py` 只采集阶段 1 验收需要的事实，不承担告警路由。shell 入口只管理 `bogda-*` 文件和服务。

## 5. 固定路径与身份

未来 Pi 使用以下默认值：

| 项目 | 值 |
|---|---|
| 服务账户 | `bogda` |
| 程序目录 | `/opt/bogda` |
| 配置目录 | `/etc/bogda` |
| 环境文件 | `/etc/bogda/bogda.env` |
| 数据根 | `/mnt/nas/.bogda` |
| Prefect Home | `/mnt/nas/.bogda/prefect` |
| SQLite | `/mnt/nas/.bogda/prefect/prefect.db` |
| 快照目录 | `/mnt/nas/.bogda/snapshots` |
| 健康证据 | `/mnt/nas/.bogda/manifests/health` |
| 本机 API | `http://127.0.0.1:4200/api` |

SQLite 必须由 Pi 本机通过 ext4 打开，不得通过 SMB 访问。`/mnt/broker` 是旧路径，部署包中不得出现。数据根不落 SD 卡。

服务账户拥有 `/mnt/nas/.bogda`，但不拥有现有 NAS 的其他目录。systemd unit 使用 `RequiresMountsFor=/mnt/nas/.bogda`，避免 SSD 未挂载时回退写入系统盘同名目录。

## 6. 秘密与网络边界

仓库只保存 `bogda.env.example` 的变量名和非秘密默认值。未来部署者在 Pi 上创建 `/etc/bogda/bogda.env`，权限为 root 可写、`bogda` 组可读；真实 Basic Auth 值不得进入 Git、manifest、健康报告或命令输出。

环境文件至少提供：

```text
PREFECT_HOME=/mnt/nas/.bogda/prefect
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_SERVER_API_AUTH_STRING=<runtime secret>
PREFECT_API_AUTH_STRING=<runtime secret>
```

Prefect Server 为未来 Tailscale 访问准备监听地址，但本部署包不修改宿舍网络、防火墙或 Tailscale ACL。真实部署前检查必须确认 API 没有直接暴露到公网；不能证明时禁止开始影子运行。

## 7. systemd 服务

### 7.1 Prefect Server

`bogda-prefect-server.service`：

- 以 `bogda` 账户运行；
- 读取 `/etc/bogda/bogda.env`；
- 要求 `/mnt/nas/.bogda` 已挂载；
- 启动 Prefect Server 3.8.3；
- 失败时由 systemd 退避重启，不在 shell 中实现重试循环；
- 不依赖或重启任何 `orchestra-*` 服务。

### 7.2 `pi-service` Worker

`bogda-pi-worker.service`：

- 在 Prefect Server 健康后启动；
- 只连接 `pi-service` work pool；
- Worker 总并发固定为 1；
- 影子阶段只接测试 deployment 与健康检查；
- 不允许任意论文仓库、CUDA 任务或 agent 循环。

部署包只准备 Worker 与 pool bootstrap 契约，不迁移现有雷达或 Broker 队列。

### 7.3 快照与健康定时器

快照 timer 每日调用 `python -m bogda.ops.snapshot`。健康 timer 默认每 5 分钟调用 `python -m bogda.ops.health sample`，将 JSON Lines 写入健康证据目录。具体日历值集中在 unit 文件，不复制进 README 的状态叙述。

## 8. SQLite 快照与恢复

快照工具使用 Python `sqlite3.Connection.backup()`，不能在 Prefect Server 运行时直接复制数据库文件。每个快照由数据库文件和相邻 JSON manifest 组成，manifest 至少记录：

- UTC 时间；
- 源数据库路径；
- 快照路径；
- 字节数；
- SHA-256；
- `PRAGMA integrity_check` 结果；
- 工具版本。

快照成功条件是 backup API 完成、快照 `integrity_check` 返回 `ok` 且 manifest 原子写入。失败时保留已有快照，不更新“latest”指针，不删除源数据库。

恢复验证在临时目录复制指定快照，验证 SHA-256 与 `integrity_check`，然后输出报告。它不覆盖现役 `prefect.db`。真正恢复必须在未来运行手册规定的停服窗口中由人确认。

本地测试使用临时 SQLite 数据库，写入已知记录后执行快照和恢复验证，证明内容与完整性一致。

## 9. 健康采样与 72 小时证据

健康采样每次输出一个 JSON 对象，至少包含：

- UTC 时间；
- Prefect API 是否可达和请求耗时毫秒；
- `/proc/meminfo` 的 `MemAvailable`；
- swap 总量与已用量；
- `/mnt/nas` 可用空间；
- Prefect SQLite 字节数和 `integrity_check`；
- Bogda units 的活动状态输入。

采样器不自行判断科研任务成功，也不创建告警系统。它只产生可汇总证据。汇总命令针对一个时间窗口输出：采样数、缺口、API 延迟分位数、最低可用内存、swap 增长、完整性失败次数和磁盘最低余量。

72 小时验收阈值沿用批准架构：

- 无 OOM；
- 无持续 swap 抖动；
- 常见 API 操作约 1 秒内完成；
- 空闲可用内存最好保持 400 MB 以上；
- Pi 重启后排队与历史仍存在；
- SQLite 快照可以恢复。

其中 400 MB 是观察指标而非单次硬失败阈值。OOM、数据库完整性失败、SSD 未挂载和快照不可恢复是硬失败。

## 10. 安装、dry-run 与回滚

`install.sh` 支持 `--dry-run`。dry-run 只读取 manifest、检查源文件和输出计划，不调用 `sudo`，不写 `/etc`、`/opt`、`/mnt/nas`，不执行 `systemctl`。

未来真机安装按以下边界执行：

1. 检查架构、Python、uv、Tailscale、SSD 挂载和可用空间；
2. 检查 `/mnt/nas/.bogda` 不在 SD 卡或 SMB 上；
3. 创建 `bogda` 服务账户与目标目录；
4. 安装锁定依赖和 `bogda-*` unit；
5. 保存被替换的 Bogda unit 备份；
6. 执行 daemon-reload，但只有显式 `--start` 才启动服务。

`rollback.sh` 只停止/禁用 `bogda-*` units，恢复部署前保存的 Bogda unit 与环境文件，并执行 daemon-reload。它不删除 `/mnt/nas/.bogda`、快照、健康证据或现有 Orchestra 文件。

部署脚本拒绝管理未以 `bogda-` 开头的 unit。它不实现原子 `releases/<sha>`、通用包管理器或跨发行版适配。

## 11. 本地验证

本阶段在 Windows 主工作站完成：

- `bundle.py` 单元测试验证路径、unit 清单、秘密占位和 dry-run 无写入；
- 临时 SQLite 快照与恢复测试；
- 健康采样与窗口汇总测试，输入使用临时文件和受控样本；
- Git Bash `bash -n` 验证 `install.sh` 与 `rollback.sh`；
- 全部现有 Bogda Python 3.11 测试回归；
- `git diff --check` 和无 Orchestra 导入检查。

本地测试不能证明 systemd、ARM64、Tailscale 或真实 SSD 行为。运行手册必须把 `systemd-analyze verify`、真机 mount 检查、Basic Auth、重启恢复和快照恢复列为部署窗口的硬门禁。

## 12. 故障语义

| 场景 | 本地部署包行为 |
|---|---|
| manifest 路径指向 `/mnt/broker` 或非 `/mnt/nas/.bogda` | 检查失败，不生成可安装计划 |
| 环境示例包含真实凭据 | 测试失败 |
| dry-run 尝试写系统路径或调用 systemctl | 测试失败 |
| SSD 未挂载 | 未来 preflight 硬失败，服务不启动 |
| SQLite 快照或完整性检查失败 | 返回非零，不更新 latest，不删除旧快照 |
| 恢复验证失败 | 返回非零，不触碰现役数据库 |
| Prefect API 暂时不可达 | 健康样本记录失败事实；不伪造服务状态 |
| 本地无法验证 systemd | 保持为真机部署门禁，不用静态测试冒充真机验收 |

## 13. 运行手册与交付物

`bogda/docs/pi-shadow-runbook.md` 明确区分：

1. 本地 bundle 构建与验证；
2. 真机部署前人工检查；
3. 安装但不启动；
4. 影子服务启动；
5. 72 小时证据收集；
6. 重启、快照和恢复演练；
7. 通过、回退 A 方案或完整回滚。

运行手册不嵌入手写测试数量、部署 SHA 或真实凭据。状态以测试输出、manifest 和真机证据为准。

## 14. 持久挂账

下列内容在后续需要，但当前不实现：

- 实际 Pi SSH 部署与 72 小时验收；
- Wake Bridge、WoL 冷却、直连网口和唤醒告警；
- 当前笔记本模拟 `dorm-x86`；
- Windows Power Agent、睡眠抑制和游戏模式；
- 雷达、通知、备份等真实 `pi-service` Flow；
- 宿舍机 CPU/GPU Worker 与总并发 1；
- SLC/pSLC SD 卡、GPU 型号和并发提高；
- 3100 正式切流与 Orchestra 只读归档；
- CLI 极端错误输入的友好错误映射；
- 超大或非本地编码 subprocess 输出的流式日志；
- `bogda-console` 完成后的独立审查、合并和合并后回归。

挂账进入 Mission 041 决策记录和后续实施计划的“明确不做”，不得只依赖会话记忆。

## 15. 完成标准

- 部署 bundle 文件结构、manifest、units、Python ops 和运行手册齐全；
- dry-run 在 Windows 本地不会写系统路径或调用系统服务；
- 临时 SQLite 快照与恢复验证通过；
- 健康采样和 72 小时汇总的纯逻辑测试通过；
- shell 语法和全部 Bogda Python 3.11 回归测试通过；
- 仓库不含真实秘密、旧 `/mnt/broker` 默认值或 Orchestra 依赖；
- 没有连接 Pi、没有修改现网、没有启动影子服务；
- 后续真机部署和暂缓能力都有持久留痕。
