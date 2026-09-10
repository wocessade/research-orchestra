# 新 Windows runner 开工（填单机写包，真机上执行）

<!-- campus-runner-status:2026-09-10 -->
> 2026-09-10 现状更新：Orchestra/3100 已停用；Y7000 已接入 WSL2、NAS 和 dorm-x86，并发 1，自主 smoke 与 WSL 重启恢复通过。checkpoint key 本地修复已测、尚未部署，DEF-03 未通过现网验收。3101 仍为只读 observer。下文历史设计/操作步骤不代表已经部署；“runner 未到手/未联网/仅雷达停用”等旧状态以[最新交接](2026-09-10-bogda-runner-handoff.md)为准。共享 SQLite 和日志发布接线仍待完成。
<!-- /campus-runner-status -->

日期：2026-09-06  
对象：刚到手的 Windows 笔记本，作为研究 worker 顶替未采购的宿舍机。  
**不是** 3100 切换。**不是** Wake Bridge / WoL。**不是** 把研究任务丢进现网 `pi-service`。  
隔壁会话若仍在改 `bogda/src`，本包只动 `bogda/deploy/runner/`，不抢源码。

握手权威仍是 [`2026-09-02-bogda-runner-handshake.md`](2026-09-02-bogda-runner-handshake.md)。

## 这台 Cursor 做不到的

当前会话在填单机 `laptop-w0cessade` 上。新电脑还不在 tailnet。从这里 SSH `rk3528` / `100.78.158.80` 超时（盒子显示约两天未活跃）。因此：**OOBE、装 Tailscale、第一次进 Ubuntu，必须你在新键盘上做。** 做完把新机拉进同一 tailnet 后，才能从这边继续，或直接在新机开 Cursor。

入学 **2026-09-08 09:00**。宿舍–实验室 Tailscale 仍挂账；新机优先加 Tailscale，不要赌校园网直连 `10.77.0.1`。

## 合同（不要改）

| 项 | 取值 |
|---|---|
| 宿主机 | Windows。只管电源、Tailscale、WSL |
| 计算环境 | **WSL2 Ubuntu**。Prefect process worker、attempt、dsh session 都在 WSL 盘 |
| 池名 | `dorm-x86`（软件契约）。这台笔电是顶替，**不是** 已上线宿舍塔 |
| 并发 | `--limit 1`，禁止加 |
| 共享文件 | `/mnt/nas/.bogda/runner/*` 与盒子 3101 同一份，不是拷贝 |
| 离线 | 研究任务保持 `Scheduled`，不准降级到 `pi-service` |
| 技能树 | 不复制本机 `~/.claude/skills` |

HMAC、Samba 密码、`PREFECT_API_AUTH_STRING` 只写进新机和盒子的环境文件。**不要贴进聊天、不要入库。**

3101 保持 `real-readonly` / `observer`，直到盒子上有**精确** deployment / queue / pool，且 HMAC 两边一致。到那一步再开口切 `allowlisted-test`。

## 你在新电脑上的顺序

### 0. 开箱（约 15 分钟）

1. 完成 Windows 初始设置，本地管理员账号。主机名可用 `runner-x86`。
2. 插电。不要开 Wake Bridge；插电不睡即可。
3. 安装 [Tailscale](https://tailscale.com/download/windows)，登录现有账号，等到状态里能看见 `rk3528`。
4. **不要**在原生 PowerShell 里装 Prefect 或当研究 worker。

### 1. Windows 宿主

管理员 PowerShell（仓库拷到新机之后，或先只跑这一段）：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
# 若仓库已在 D:\pythonProject：
.\bogda\deploy\runner\bootstrap-windows.ps1
```

开了 WSL 功能就重启。重启后打开一次 Ubuntu，建 UNIX 用户。

### 2. 把仓库放到 WSL 盘

在 Ubuntu 里 clone，路径不要落在 `/mnt/c`：

```bash
sudo apt-get update && sudo apt-get install -y git
mkdir -p "$HOME/src"
git clone git@github.com:wocessade/research-orchestra.git "$HOME/src/research-orchestra"
cd "$HOME/src/research-orchestra"
bash bogda/deploy/runner/bootstrap-wsl.sh
```

私仓要用你已有的 GitHub 密钥或 `gh auth`。代理跟填单机同一套，不写进脚本。

### 3. 只在机器上填的值

1. `~/.config/bogda/nas.cred`：Samba 用户 `liuxfs`，密码自己填，`chmod 600`。
2. `~/.config/bogda/runner.env`：
   - `PREFECT_API_AUTH_STRING` 从盒子 `/etc/bogda/bogda.env` **拷到新机**，不要经过聊天。
   - `BOGDA_APPROVAL_HMAC_KEY`：在新机或盒子上 `python -c "import secrets; print(secrets.token_hex(32))"`，**两边同一把**。
3. `bash bogda/deploy/runner/mount-nas.sh`  
   若缺 `/mnt/nas/.bogda/inbox` 等目录：先在盒子上 `sudo bash bogda/deploy/shared/prepare_runner_share.sh`。
4. `bash bogda/deploy/runner/start-worker.sh`  
   应看到 pool `dorm-x86`、limit 1 的 process worker。
5. 另开一个壳：`bash bogda/deploy/runner/print-handshake-ids.sh`  
   精确 ID 写进盒子 3101 环境。禁止 `*`，禁止把 `pi-service` 填进研究白名单。

### 4. 验收（worker 活着之后）

对照握手文档短清单：基础设施页能看到 pool/queue/heartbeat；日志根目录对上；>20 CNY `consume_open` 一次；清理留 tombstone。**DEF-03 checkpoint 要等 worker 真挂起**，空跑不算过。

## 明确不做

- 改 3100
- 研究 Flow 进 `pi-service`
- 本机 skill 整棵同步到 runner
- 把 HMAC / Prefect auth 写进仓库或对话
- 未开口就删盒子 S2 验收资源
- 把这台笔电写成已接入的宿舍塔 / Wake Bridge
