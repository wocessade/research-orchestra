# Bogda RK3528 Gate 6：e2fsck 修复与重试运行日志

日期：2026-08-30（北京）

状态：已完成；trial `20260830T154019Z` 于 2026-08-31 通过 Gate 6。

## 授权与边界

Owner 已授权推进 Gate 6，包括修复 RK3528 上的 ext4 检查器、离线检查数据盘、正常依赖挂载、受控重启、独立恢复演练和新一轮 24 小时试运行。

本轮明确不做：修改 `/etc/fstab`、格式化磁盘、自动修复未经解释的文件系统错误、覆盖 live `prefect.db`、升级整套操作系统、添加第三方软件源。

## 故障结论

- 数据盘：`/dev/sda1`，ext4，UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f`，挂载点 `/mnt/nas`。
- RK3528：Armbian 26.2.1 Jammy，aarch64，内置 `e2fsck 1.46.5`。
- 文件系统特性 `FEATURE_C12` / `FEATURE_R16` 分别对应 `orphan_file` / `orphan_present`；支持始于 e2fsprogs 1.47.0。
- Jammy 软件源候选版本仍为 `1.46.5-2ubuntu1.2`，常规升级不能解决。
- 旧检查器令 systemd fsck unit 失败；此前通过 `--job-mode=ignore-dependencies` 得到的挂载不计入 Gate 6 验收。

## 选定修复

使用 Ubuntu 官方 Noble Updates 的 ARM64 静态检查器，不跨装 Noble 的动态 e2fsprogs：

- package：`e2fsck-static`
- version：`1.47.0-2.4~exp1ubuntu4.1`
- URL：`https://ports.ubuntu.com/ubuntu-ports/pool/universe/e/e2fsprogs/e2fsck-static_1.47.0-2.4~exp1ubuntu4.1_arm64.deb`
- SHA-256：`0a3d402fd7c7c07f63b8104d84a47378f57022e7c816190e6cc99950492d8cae`

静态二进制独立安装到 `/opt/e2fsck-static-1.47.0/`，只对 `/sbin/fsck.ext4` 做可逆 diversion；Jammy 的其他 e2fsprogs 工具保持不变。

回滚路径：删除新软链接，再执行 `dpkg-divert --rename --remove /sbin/fsck.ext4`，恢复原有 `/sbin/fsck.ext4 -> e2fsck`。

## 执行记录

### 1. 前置检查

- [x] SSH host key 使用独立 known-hosts 文件严格校验。
- [x] `sudo -n` 可用。
- [x] 数据盘当前为 ext4、rw，UUID 与预期一致。
- [x] 文件系统头显示 clean；问题是旧用户态工具不识别新特性。
- [x] 当前 Gate 6 trial 因重启、断档和绕过依赖挂载而作废，不能复用。
- [x] Luna 完成只读预检；结论为不能使用 Jammy 常规升级或跨装 Noble 动态包。

### 2. 静态检查器部署

- [x] 官方包下载、版本/架构和 SHA-256 校验。
- [x] 提取后确认是 ARM64 静态二进制、版本为 1.47.0。
- [x] 对当前设备进行只读识别测试，不再出现 unknown feature。
- [x] 安装到 `/opt` 并完成 `/sbin/fsck.ext4` 可逆切换。

执行结果：包 SHA-256 与预期完全一致；`ldd` 返回 `not a dynamic executable`；`e2fsck -V` 返回 1.47.0。在线 `-fn` 已通过全部五个检查阶段，不再拒绝 `orphan_file`，但因文件系统当时仍挂载，报告了 free block/inode 计数差异和待清理 `orphan_present`。这些在线结果不作为损坏结论，也未执行任何写入修复。

当前切换：

- `/opt/e2fsck-static-1.47.0/e2fsck.static`：新静态检查器。
- `/sbin/fsck.ext4`：指向上述静态检查器。
- `/sbin/fsck.ext4.jammy-1.46.5`：原有 `fsck.ext4 -> e2fsck`。
- `dpkg-divert --list /sbin/fsck.ext4` 已确认 diversion 生效。

### 3. 离线检查与正常挂载

- [x] 记录 live DB SHA-256 和 unit 状态。
- [x] 停止 Bogda 服务及定时器，确认没有未解释的占用者。
- [x] 正常卸载 `/mnt/nas`。
- [x] 运行离线 `e2fsck -fn /dev/sda1`；无需写入修复。
- [x] 不使用 `ignore-dependencies`，让 systemd fsck + mount 正常完成。
- [x] 核对 fsck unit、rw 挂载、UUID、服务、定时器和 `/api/health`。

离线检查结果：`e2fsck 1.47.0` 完成 Pass 1–5，退出码 0；`nas-data: 525/15269888 files, 1393476/61049088 blocks`。未执行写入修复。

正常依赖挂载结果（UTC 15:38）：systemd 日志为 `nas-data: clean`，fsck unit `Result=success`、`ExecMainStatus=0`；`mnt-nas.mount` 为 `active/mounted`，`/dev/sda1` ext4 `rw`，UUID 与预期一致。server、worker、health timer、snapshot timer 全部 active，`/api/health` 返回 `true`。

live `prefect.db` 在维护前后 SHA-256 均为 `aee98aa10579a5e53101c35cf6efc5eea801e0ad56596ad2179529e69e2e2e31`。

### 4. Gate 6 新试运行

- [x] 归档旧 `samples.jsonl`，生成并记录新 trial id。
- [x] 执行一次受控重启，验证带盘自动 fsck、挂载和服务恢复。
- [x] 在独立目录完成 snapshot restore verify，不覆盖 live DB。
- [x] 继续采集 24 小时并最终执行 `health summarize`。

新 trial：`20260830T154019Z`。旧 trial `20260830T034154Z` 的 63,639-byte `samples.jsonl` 已归档为 `archive/samples-20260830T034154Z.jsonl`。首样本时间 `2026-08-30T15:40:20.419427Z`，`api_ok=true`、`database_integrity=ok`、`oom_kill_count=0`、swap 使用量 0，server/worker/timers 状态符合预期。

24 小时最早截止时间：`2026-08-31T15:40:20.419427Z`（北京时间 2026-08-31 23:40:20）。

受控重启于 UTC 15:40 发出，约 17 秒后 SSH 恢复。新 boot 的 systemd fsck 日志为 `nas-data: clean, 526/15269888 files, 1393477/61049088 blocks`；fsck unit `Result=success`、`ExecMainStatus=0`。无需人工挂载，`/dev/sda1` 按预期 UUID 自动成为 ext4 `rw`；server、worker、两个 timer 均恢复 active，`/api/health=true`。

重启后的第二个健康样本时间为 `2026-08-30T15:42:51.286942Z`：`api_ok=true`、`database_integrity=ok`、`oom_kill_count=0`、swap 使用量 0。

独立恢复演练：

- snapshot：`/mnt/nas/.bogda/snapshots/prefect-20260830T154230Z.db`
- snapshot SHA-256：`4fd08d2369bda0b4650719c95fdca2adfe105d539364d109cfedcab30dd8365f`
- snapshot / restore `integrity_check`：均为 `ok`
- restore：`/mnt/nas/.bogda/restore-drill-20260830T154019Z/prefect-restored.db`
- live DB SHA-256：仍为 `aee98aa10579a5e53101c35cf6efc5eea801e0ad56596ad2179529e69e2e2e31`，未被覆盖

命令行出现一次 Python `runpy` 模块已导入警告，但 create/verify 均返回有效 JSON、退出码 0；该警告记入后续可维护性清单，不影响本次数据完整性结果。

## 后续必要事项

- [x] 24 小时窗口结束后，逐字段核对采样跨度、缺失区间、API、数据库、磁盘、内存、swap 与 OOM 证据。
- [x] 核对所有样本中的受控 unit 状态，并复查当前 mount、fsck、服务重启计数、内核错误与服务 warning 日志。
- [x] 重新只读校验 snapshot 与独立 restore 的 SHA-256 和 SQLite integrity。
- [x] 形成[最终 Gate 6 验收报告](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)。

后续只剩 Gate 6 之外的产品接线与迁移裁决；不得把本次通过解释为自动授权 3100 切换或真实 Prefect 写入。
