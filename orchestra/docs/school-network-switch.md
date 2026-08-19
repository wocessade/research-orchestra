# 学校网络切换清单（宿舍/实验室）

> 编写：2026-08-19（mission 026 D13）| 目的：入学（2026-09）后把整套系统从家庭 LAN 切换到校园网的最小操作手册。

## 0. 切换前必做（一次）

- [ ] 改弱密码（宿舍网是共享环境）：4B `liuxfs`（现 123456）、核桃派 `pi`（现 pi）→ `passwd` 修改
- [ ] 确认 Tailscale 三端仍在线：`tailscale status`（4B=liuxfs、核桃派=walnutpi、Windows=laptop-w0cessade）
- [ ] 本机记录新网络环境：宿舍网段/网关、实验室网段、两 Pi 新 IP（如有）

## 1. 依赖 IP 的配置点盘点

| 配置点 | 位置 | 现值 | 切换动作 |
|---|---|---|---|
| Broker 上报目标 | 4B `/home/liuxfs/broker/config.json` 的 `api_url` | `http://192.168.0.200:5000` | 改 tailnet 名 `http://walnutpi.<tailnet>.ts.net:5000` 或新 IP |
| sync/deploy 脚本 | Windows env `ORCHESTRA_SSH_HOST` | `192.168.0.250` | 改 `liuxfs.<tailnet>.ts.net`（env 驱动，零代码改动） |
| usage-monitor 部署 | `deepseek-usage-monitor/usage-monitor/deploy_to_pi.py` 默认值 | `192.168.0.200` | 改 tailnet 名或传 `PI_HOST` env |
| Windows known_hosts | `~/.ssh/known_hosts` | 按 IP | tailnet 名首次连接会重新确认指纹（正常） |
| 4B/核桃派 静态 IP | Pi 网络配置 | 192.168.0.250/.200 | 宿舍网可能不允许静态 → 改 DHCP，靠 tailnet 名寻址 |
| SMB 共享 | Windows 映射 | `\\192.168.0.250\nas` | 改 `\\liuxfs.<tailnet>.ts.net\nas`（tailnet 上 SMB 走加密隧道） |

## 2. 决策树（入学后按实测拓扑选路）

```
宿舍↔实验室互通测试（互 ping）
  ├─ 互通（同一园区网）→ LAN 直连可用：只需更新 IP 引用（清单 §1 各点改新 IP）
  └─ 不互通（客户端隔离/不同网段）→ 全量切 Tailscale：
      1. ORCHESTRA_SSH_HOST=liuxfs.<tailnet>.ts.net
      2. 4B config.json api_url 改 walnutpi.<tailnet>.ts.net:5000
      3. deploy_to_pi.py 默认值改 tailnet 名
      4. 验证：sync_push/pull 全链路 + 墨水屏上报节奏正常
```

## 3. 回退步骤（Tailscale 出问题时）

1. `ssh liuxfs@<新IP>` 用 LAN 直连确认两 Pi 物理可达
2. `sudo systemctl status tailscaled`（异常时 `sudo systemctl restart tailscaled`）
3. 临时把 `ORCHESTRA_SSH_HOST` 改回 LAN IP，其余配置点不动（Tailscale 恢复后自动可用）

## 4. 切换后验证清单

- [ ] `sync_push.sh`/`sync_pull.sh` 正常（顺带 last_sync 上报）
- [ ] 墨水屏状态条 `Broker OK`、任务列表有数据（上报链路通）
- [ ] 微信/QQ 邮件通知不受影响（Pi 直发，与外网可达性有关，与内网拓扑无关）
- [ ] Windows 脱机测试一次（服务面照常）

## 5. 其它提醒

- 1A 适配器只给核桃派用；4B 必须 5V/3A（2026-08-19 事故教训：1A 供电导致 4B 用户态整体死亡）
- 校园网 LLM API/文献源可达性入学后实测；不可达时 Windows v2rayN 兜底（Pi 可配 HTTPS_PROXY 走本机）
