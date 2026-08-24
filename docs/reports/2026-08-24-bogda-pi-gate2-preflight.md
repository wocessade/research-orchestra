# Bogda Pi Gate 2 预检证据（只读）

日期：2026-08-24

执行者：本会话（Cursor / Grok）

仓库：`D:\pythonProject`

基线：`ace09735920af57e8a627210b0e5b7c3ff2d7197`（`git rev-parse HEAD`；短号 `ace0973`；`docs(bogda): record Pi bundle merge checkpoint`）

Pi：`ssh liuxfs@100.111.75.58`（BatchMode，无 sudo）

临时 unit 目录：`/tmp/bogda-gate2-ace0973`（本预检未删除）

约束：未安装、未启动、未改 systemd、未写 `/etc` 或 `/mnt/nas`、未暂停/取消 Orchestra 任务。

总判断：**主机与挂载事实通过；Bogda 尚未安装；`systemd-analyze verify` 按 systemd 字面退出码为 1，原因是安装后才存在的 ExecStart/ExecStartPre 路径，不是 Bogda unit 语法错误。** 与 runbook「安装前 verify 必须接受全部六份 unit」存在设计矛盾。本文不改 runbook，只记录建议。

---

## 1. Codex 只读事实复核

采集窗口：2026-08-24T05:59:12Z–06:04:16Z（Pi 本地 CST +0800）。

| 声称 | 实测 | 命令 / 时间 / 退出码 | 结论 |
|---|---|---|---|
| aarch64 | `aarch64` | `uname -m` 05:59:12Z exit=0 | 通过 |
| Debian 13 trixie | `PRETTY_NAME="Debian GNU/Linux 13 (trixie)"`；`VERSION_ID=13`；`VERSION_CODENAME=trixie`；`DEBIAN_VERSION_FULL=13.5` | `cat /etc/os-release` 05:59:12Z exit=0 | 通过 |
| Python 3.13.5 | `Python 3.13.5`；`3.13.5 (main, May  5 2026, 21:05:52) [GCC 14.2.0]` | `python3 --version` 05:59:12Z exit=0；带引号的 `python3 -c 'import sys; print(sys.version); assert sys.version_info >= (3, 11), sys.version'` 06:02:44Z exit=0 | 通过（≥3.11） |
| `/mnt/nas` = `/dev/sda1` ext4 | `SOURCE=/dev/sda1 FSTYPE=ext4 UUID=d105381a-d80e-47b0-8bb4-2a8c4b56600f` | `findmnt -no SOURCE,FSTYPE,UUID --target /mnt/nas` 05:59:12Z exit=0 | 通过 |
| UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f` | 同 UUID；`PARTUUID=904d6213-01`；磁盘 `SERIAL=19336B804557` | `lsblk -o NAME,SERIAL,UUID,PARTUUID,FSTYPE,MOUNTPOINTS` 05:59:13Z exit=0 | 通过 |
| fstab 使用相同 UUID | 第 5 行：`UUID=d105381a-d80e-47b0-8bb4-2a8c4b56600f /mnt/nas ext4 defaults,nofail 0 2` | `grep -nE 'mnt/nas|d105381a' /etc/fstab` 06:02:44Z exit=0 | 通过 |
| 可用空间约 232 GB | `Avail=232469512192` 字节（约 232.47 GB / 216.50 GiB）；`df -h`：Size 229G Used 4.8M Avail 217G | `df -B1 --output=source,avail,target /mnt/nas` 05:59:13Z exit=0 | 通过 |
| MemAvailable 约 1.46 GB | `MemAvailable: 1445156 kB`（约 1.48 GB / 1.38 GiB）；`MemTotal: 1892032 kB` | `grep -E '^(MemTotal\|MemFree\|MemAvailable\|SwapTotal\|SwapFree):' /proc/meminfo` 05:59:13Z exit=0 | 通过；远高于 400 MB 观察阈 |
| Tailscale IPv4 `100.111.75.58` | `100.111.75.58` | `tailscale ip -4` 06:00:26Z exit=0 | 通过 |
| `tailscale serve` 未配置 | `No serve config` | `tailscale serve status` 06:00:26Z exit=0 | 通过 |
| `orchestra-broker` active | `active`；`active (running)` since 2026-08-23 09:49:15 CST；Main PID 1029 `/usr/bin/python3 /home/liuxfs/broker/dispatcher.py` | `systemctl is-active orchestra-broker.service` 06:00:25Z exit=0；`systemctl status --no-pager --lines=20 orchestra-broker.service` 06:00:25Z exit=0 | 通过 |
| 未安装 Bogda | `/opt/bogda`、`/etc/bogda`、`/mnt/nas/.bogda` 均不存在；`bogda-*` unit 0 个 | `ls -ld /opt/bogda /opt/bogda/.venv/bin/python /opt/bogda/.venv/bin/prefect /etc/bogda /etc/bogda/bogda.env` 05:59:13Z exit=2；三路径 `test -e` EXISTS=0；`systemctl list-unit-files --no-pager 'bogda-*'` 06:00:25Z exit=1（0 unit files） | 通过 |

附加主机事实：

- 内核：`Linux liuxfs 6.18.34+rpt-rpi-v8 #1 SMP PREEMPT Debian 1:6.18.34-1+rpt1 (2026-06-09) aarch64 GNU/Linux`（`uname -a` 05:59:12Z exit=0）
- systemd：`systemd 257 (257.13-1~deb13u1)`（`systemd-analyze --version` 06:02:44Z exit=0）
- Tailscale JSON 子集 06:00:28Z exit=0：`BackendState=Running`；`Version=1.102.2-t6cac91817-g6ff0ddc72`；`Self.HostName=liuxfs`；`Self.DNSName=liuxfs.tail6d8b09.ts.net.`；`Self.TailscaleIPs=['100.111.75.58','fd7a:115c:a1e0::f101:4bda']`；`Self.Online=True`；`MagicDNSSuffix=tail6d8b09.ts.net`；`CurrentTailnet.Name=wocessade.github`；`PeerCount=2`；无 Exit Node
- `tailscale netcheck` 06:00:26Z–06:00:28Z exit=0：UDP true；IPv4 `114.222.12.87:53115`；IPv6 `[240e:3a3:3b:9590:d908:12d0:7c52:749a]:46050`；PortMapping UPnP；Nearest DERP San Francisco
- fstab 另有已注释的旧行：`# UUID=790ffa98-7243-4c44-94e7-ade236a5a5c1 /mnt/broker ext4 ...`（`cat /etc/fstab` 06:02:44Z exit=0）
- 根分区在 microSD：`mmcblk0p2` UUID `8abab6b9-ef90-4fee-ae3d-91079bfae7c1` 挂 `/`；数据盘是 USB/SSD `sda1` 挂 `/mnt/nas`

---

## 2. 临时 unit 目录与 `systemd-analyze verify`

六份文件仍在 `/tmp/bogda-gate2-ace0973`（`ls -la` 05:59:13Z 与 06:02:44Z 均为 exit=0）：

| 文件 | 字节 |
|---|---|
| `bogda-pi-worker.service` | 714 |
| `bogda-prefect-server.service` | 483 |
| `bogda-prefect-snapshot.service` | 542 |
| `bogda-prefect-snapshot.timer` | 179 |
| `bogda-shadow-health.service` | 498 |
| `bogda-shadow-health.timer` | 187 |

`sed` 转储显示 CRLF（`[Unit]\r`）。systemd 仍能解析；Gate 3 安装到 `/etc/systemd/system` 时应保证 LF。本预检未改这些文件。

Exec 目标（与仓库 `bogda/deploy/pi/systemd/` 一致）：

- server：`/opt/bogda/.venv/bin/prefect server start --host 0.0.0.0 --port 4200`
- worker：`ExecStartPre=/opt/bogda/.venv/bin/python -m bogda.ops.health wait-api ...`；`ExecStart=/opt/bogda/.venv/bin/prefect worker start ...`
- snapshot / health：`/opt/bogda/.venv/bin/python -m bogda.ops.snapshot|health ...`
- `EnvironmentFile=/etc/bogda/bogda.env`；`User=bogda`；`RequiresMountsFor=/mnt/nas/.bogda`

### 2.1 必须捕获的 glob verify

远端 shell 内（glob 展开后）执行：

```sh
systemd-analyze verify /tmp/bogda-gate2-ace0973/*.service /tmp/bogda-gate2-ace0973/*.timer
rc=$?
printf 'verify_exit=%s\n' "$rc"
```

时间：2026-08-24T05:59:13Z
**`verify_exit=1`**

完整 stderr：

```
/etc/systemd/system/orchestra-timer.timer:7: Unknown key 'Timezone' in section [Timer], ignoring.
/etc/systemd/system/orchestra-housekeeping.timer:7: Unknown key 'Timezone' in section [Timer], ignoring.
/etc/systemd/system/orchestra-backup.timer:7: Unknown key 'Timezone' in section [Timer], ignoring.
/etc/systemd/system/nas-backup.timer:7: Unknown key 'Timezone' in section [Timer], ignoring.
bogda-pi-worker.service: Command /opt/bogda/.venv/bin/python is not executable: No such file or directory
bogda-pi-worker.service: Command /opt/bogda/.venv/bin/prefect is not executable: No such file or directory
bogda-prefect-server.service: Command /opt/bogda/.venv/bin/prefect is not executable: No such file or directory
bogda-prefect-snapshot.service: Command /opt/bogda/.venv/bin/python is not executable: No such file or directory
bogda-shadow-health.service: Command /opt/bogda/.venv/bin/python is not executable: No such file or directory
```

未出现 Bogda unit 的 Unknown key / 非法 section。未报告缺失的 `EnvironmentFile=/etc/bogda/bogda.env` 或用户 `bogda`（二者同样尚未创建）。

### 2.2 逐文件 verify（06:00:24Z–06:00:25Z）

| unit | verify_exit | Bogda 自身消息 |
|---|---|---|
| `bogda-pi-worker.service` | 1 | python + prefect 不存在 |
| `bogda-prefect-server.service` | 1 | prefect 不存在 |
| `bogda-prefect-snapshot.service` | 1 | python 不存在 |
| `bogda-shadow-health.service` | 1 | python 不存在 |
| `bogda-prefect-snapshot.timer` | 0 | 无 Bogda 命令错误 |
| `bogda-shadow-health.timer` | 0 | 无 Bogda 命令错误 |

每个命令仍打印四条 Orchestra/NAS timer 的 Timezone 警告。两个 Bogda timer 的 exit=0 表明这些警告被 ignoring，不单独把 Bogda timer 判失败。

---

## 3. 三类问题的区分

### A. Bogda unit 语法 / 字段问题

**未观察到。** 六份临时 unit 没有 Unknown key、未知 section 或解析失败。失败行全部是 ExecStart/ExecStartPre 指向的二进制。

### B. 因尚未安装而缺少 `/opt/bogda/.venv/bin/{python,prefect}`

**这是 `verify_exit=1` 的全部 Bogda 原因。** 与 `ls`：这些路径 No such file or directory（05:59:13Z exit=2）一致。这是 Gate 3 `install.sh --install` 之前的预期主机状态，不是 unit 写错。

### C. 现有 Orchestra timer 的 Timezone 警告

**与 Bogda 无关的既有主机噪声。** `systemd-analyze verify` 在解析任意 unit 时仍会加载已安装 timer 图，因此四条警告来自：

- `/etc/systemd/system/orchestra-timer.timer:7`
- `/etc/systemd/system/orchestra-housekeeping.timer:7`
- `/etc/systemd/system/orchestra-backup.timer:7`
- `/etc/systemd/system/nas-backup.timer:7`

systemd 257 对 `[Timer]` 的 `Timezone=` 报 Unknown key 并 **ignoring**。单独 verify 两个 Bogda timer 时仍 exit=0。不应把这四条算作 Bogda Gate 2 硬失败。本预检未改这些 timer。

---

## 4. Gate 2 设计矛盾与最小建议（不改文件）

Runbook（`bogda/docs/pi-shadow-runbook.md` Gate 2）要求安装前：

> `systemd-analyze verify` must accept all six reviewed unit files … this command is the future Pi gate for actual systemd parsing **and command resolution**.

同一套 unit 的 `ExecStart`/`ExecStartPre` 指向 `/opt/bogda/.venv/bin/python` 与 `/opt/bogda/.venv/bin/prefect`，这些文件只在 Gate 3 `deploy/pi/install.sh --install` 之后才应存在。Gate 3 才对 `/etc/systemd/system/bogda-*.{service,timer}` 再跑一次 verify。

实测：解析成功；命令解析失败；字面「accept」= exit 0 **在安装前不可能成立**。

**不要擅自改 runbook / unit。** 建议（最小）：

1. **采用 A+B，不要只选 A。**
   - **Gate 2 预期（A）**：六份 unit **解析成功**；允许且应当出现「`/opt/bogda/.venv/bin/{python,prefect}` is not executable: No such file or directory」；`verify_exit=1` 在此分类下 **不是** Bogda 语法失败。Orchestra Timezone 警告忽略。若出现 Bogda unit 的 Unknown key / 非法字段，才硬失败。
   - **Gate 3 安装后、启动前（B）**：对已安装到 `/etc/systemd/system` 的六份 unit 再跑 verify，**要求上述 command-not-executable 行消失**。这才是 command-resolution 硬门。此时仍应忽略 Orchestra Timezone 警告，或单独记为既有主机债。

2. **不要只把 Gate 2 改成「exit 1 也算过」而不把 command-resolution 挪到 Gate 3**：那会丢掉「venv 二进制确实装上了」的检查。

3. **方案 C（可选，仍最小）**：Gate 2 增加一个 stderr 分类器，而不是换掉 `systemd-analyze verify`。规则：Bogda 未知字段 → 失败；仅缺失 `/opt/bogda/.venv/bin/*` → 预期；Orchestra `Timezone` ignoring → 噪声。比改 ExecStart 做占位二进制更干净。

**本次不改 runbook。** 在 A+B 被写进 runbook 之前，**不应把字面 `verify_exit=0` 当成 Gate 2 主机硬失败**；主机预检本身已完成。进入 Gate 3 仍须另一次授权窗口（sudo、写 `/opt` `/etc`、创建 `bogda` 用户与 `/mnt/nas/.bogda`）。

---

## 5. Tailscale、监听端口、防火墙（只读，未改规则）

### 监听（`ss -lntup` / `ss -lnt`，06:00:26Z exit=0）

进程名列为空（非 root 常见）。TCP 监听摘要：

| 地址:端口 | 说明 |
|---|---|
| `0.0.0.0:22` / `[::]:22` | SSH |
| `0.0.0.0:445` / `139` 及 IPv6 对应 | Samba |
| `0.0.0.0:111` / `[::]:111` | rpcbind |
| `*:5900` | VNC |
| `100.111.75.58:39539` | Tailscale 侧 TCP |
| `[fd7a:115c:a1e0::f101:4bda]:40481` | Tailscale IPv6 侧 |

**没有 TCP 4200。** Prefect server 未监听，符合未安装。

UDP 含 5353、41641、111、137/138（NetBIOS）及 IPv6 对应项。

### Tailscale

- `tailscale status` 06:00:26Z exit=0：
  - `100.111.75.58  liuxfs            wocessade@  linux`
  - `100.103.79.3   laptop-w0cessade  wocessade@  windows  active; direct 192.168.0.186:41641`
  - `100.64.2.60    walnutpi          wocessade@  linux`
- `tailscale serve status`：`No serve config` exit=0
- `tailscale ip -6`：`fd7a:115c:a1e0::f101:4bda` exit=0
- 未见把 4200 暴露为 serve 的配置

### 防火墙

登录用户 `PATH=/usr/local/bin:/usr/bin:/bin:/usr/games`，因此裸命令 `nft`/`iptables`/`ufw` 为 command not found（06:00:28Z exit=127）。**不是未安装 nftables：**

- `/usr/sbin/nft` 与 `/sbin/nft` 存在（`ls -l` 06:02:44Z；因缺 ufw/firewalld，该 ls 总 exit=2）
- `/usr/sbin/iptables` → `/usr/sbin/xtables-nft-multi`

无 sudo 调用：

| 命令 | 时间 | 退出码 | 结果 |
|---|---|---|---|
| `/usr/sbin/nft list ruleset` | 06:04:16Z | 1 | `Operation not permitted (you must be root)` |
| `/usr/sbin/iptables -S` | 06:04:16Z | 4 | `Permission denied (you must be root)` |
| `ufw status` | 06:00:28Z | 127 | 未安装（PATH 与 `/usr/sbin/ufw` 均无） |

**未修改防火墙。** 规则转储只能放到已授权的 Gate 4（runbook 已写 `sudo nft list ruleset`）。当前只能记录：工具在 sbin、非 root 读不了 ruleset、无 ufw。

---

## 6. Orchestra 在途任务（只读，未暂停/取消/改卡）

数据根：`/home/liuxfs/broker-data`（不是 `/mnt/nas`）。

| 检查 | 结果 |
|---|---|
| `systemctl is-active orchestra-broker.service` | active，exit=0 |
| `tasks/` 顶层 `T-*.md` | 无（`find ... -maxdepth 1` 06:00:28Z exit=0，无输出） |
| 仅有 `tasks/archive/` | 最近为 2026-08-23 夜间雷达四阶段，已归档 |
| `results/**/state.json` | 26 份；`explicit_inflight_count=0`；最近 8 份 `status=done`（08-22/08-23 雷达） |
| timers | `orchestra-timer.timer` 下次 2026-08-24 23:30 CST；`orchestra-backup.timer` 次日 03:00；`nas-backup.timer` 04:17；`orchestra-housekeeping.timer` 周日 04:00。均为 waiting |

**结论：没有在途 Orchestra 任务。** 未执行 pause/cancel/inject/deploy。夜间雷达今晚 23:30 仍会按 timer 注入；本预检未触碰该 timer。

---

## 7. 通过 / 阻塞 / 风险 / Gate 3 前置

### 通过项

- 架构 aarch64、Debian 13.5 trixie、Python 3.13.5 ≥ 3.11
- `/mnt/nas` 为本地盘 `/dev/sda1` ext4，UUID 与 fstab 一致，约 232 GB 可用
- 内存观察阈通过（MemAvailable ≈ 1.48 GB）
- Tailscale 在线，IPv4 为 `100.111.75.58`，serve 未配置，无 4200 监听
- Orchestra broker 在跑且队列为空
- Bogda 未安装、无 bogda unit files
- Bogda 临时 unit **语法可解析**；两个 timer verify_exit=0

### 非主机故障、但 runbook 字面不满足

- glob `systemd-analyze verify` **`verify_exit=1`**，仅因 venv 命令尚不存在
- 在 runbook 改写预期之前，**不要把「verify 必须 exit 0」当成 Gate 2 主机硬失败**；也不要假装已经做完 command-resolution

### 进入 Gate 3 的前置条件（需另一次授权）

- owner 确认 A+B（或选定的分类器 C）写入 runbook
- 允许 sudo 的安装窗口：创建 `bogda` 用户/组、写 `/opt/bogda`、`/etc/bogda`、`/mnt/nas/.bogda`、安装 unit、**仍不 `--start`**
- 安装后立刻在 `/etc/systemd/system` 上重跑 verify，确认 command-not-executable 行消失
- 运行时 env 与 Basic Auth 仍按 Gate 4；本预检未碰
- 安装脚本须把 unit 写成 LF；`/tmp` 副本目前是 CRLF
- 队列在安装窗口仍应为空，或明确接受与夜间雷达/备份 timer 重叠的风险（23:30 / 03:00 / 04:17）

### 风险（记录，未处理）

- 临时 unit 含 CRLF
- Python 3.13.5 满足「≥3.11」；与 Prefect 3.8.3 的真机兼容是 Gate 3 venv 问题
- 非 root 看不到防火墙规则；公开暴露检查仍属 Gate 4
- 主机已监听 SSH/Samba/VNC/rpcbind；Bogda 不应在本阶段改它们
- `ss -lntup` 无进程名，不影响「4200 未监听」结论
- Orchestra timer `Timezone=` 在 systemd 257 上无效并被忽略；可能造成「以为按指定时区、实际按系统时区」。与 Bogda 无关，但是既有债
- MemTotal 约 1.89 GB；Prefect server+worker 与 broker 共存需在 72h 观察里看 OOM，Gate 2 只记录观察阈已过
- `/mnt/nas/.bogda` 尚不存在；`RequiresMountsFor=/mnt/nas/.bogda` 在目录创建前会怎样，要在 Gate 3 安装脚本里验证，本预检未 start

---

## 8. Runbook 修改建议（已停下，未改）

建议只改 `bogda/docs/pi-shadow-runbook.md` Gate 2 / Gate 3 两段预期，不改 unit 的 ExecStart：

- Gate 2：把「must accept」改成「解析成功 + 允许缺失 `/opt/bogda/.venv/bin/{python,prefect}` + 忽略非 `bogda-` 的 Timezone ignoring」；要求在远端 shell 记录 `rc=$?` 与 `verify_exit=`。
- Gate 3：`--install` 之后、任何 `--start*` 之前，verify **必须不再**报告这些路径 not executable。
- 不要为了让 Gate 2 exit 0 而改成 `/usr/bin/true` 占位。

等待 Codex / owner 选定 A+B 或分类器 C 后再改文档。

---

## 9. 本预检明确未做

未运行 `install.sh --install` / `--start` / `--start-server` / `--start-services`。

未 sudo、未重启、未停 Pi、未停 Orchestra、未写 `/etc` 或 `/mnt/nas`。
未删除 `/tmp/bogda-gate2-ace0973`。

---

## 10. 仓库改动

本预检只新增本报告：`docs/reports/2026-08-24-bogda-pi-gate2-preflight.md`。

工作树在基线 `ace0973` 上另有既有未提交项（非本任务）：`.gitignore` 修改、两份锐评删除、`.codegraph/`、`esp32c3-weather/`、两份 superpowers 天气文档、两张 Orchestra 任务卡。

**未 commit、未 push、未合并 main。** 本报告如需入库，可单独提交到 `codex/` 分支；需 owner 开口后再做。
