# Orchestra 冻结（runner 到手前）

日期：2026-09-02（北京约 01:40）  
授权：owner 允许暂停部分或全部 Orchestra 功能，把 Bogda 软件推到接 runner 之前。

**不是 3100 切换。不是停 Prefect。不是停 NAS。不是删 S2 验收资源。**

## 现网实际停了什么

主机：RK3528，SSH `liuxfs@100.78.158.80`。

| unit | 冻结前 | 冻结后 | 原因 |
|---|---|---|---|
| `orchestra-timer.timer` | enabled / active | **disabled / inactive** | 停夜间雷达注入，给 runner 到来前让出盒子与注意力 |
| `orchestra-broker.service` | enabled / active | **未动** | 3100 / exam 告警仍要队列心跳 |
| `orchestra-exam-watch.timer` | enabled / active | **未动** | 入学（2026-09-08）雨课堂仍要轮询 |
| `orchestra-backup.timer` | enabled / active | **未动** | 不停盘内备份 |
| `orchestra-housekeeping.timer` | enabled / active | **未动** | 周日清理仍要 |
| `bogda-prefect-server` / `bogda-pi-worker` | active | **未动** | 控制面继续活着；研究任务仍禁 `pi-service` |
| Samba / 3100 | 在役 | **未动** | |

执行（已做）：

```sh
sudo systemctl disable --now orchestra-timer.timer
```

盒子已回报：`Removed .../timers.target.wants/orchestra-timer.timer`，`disabled` + `inactive`。

## 软件合入（本记录同时生效）

- `codex/bogda-now06-pre-research`：3101 身份 / 日志 / 清理 / >20 CNY 签发 / usage-unknown / 审批库
- `wip/local-main-salvage`：Tailscale SSH、宿舍 runner 停购、remount 合同、08-30 过程报告、RF PCB
- 握手：[`2026-09-02-bogda-runner-handshake.md`](2026-09-02-bogda-runner-handshake.md)

runner 到手前 **不再** 开 Orchestra 新功能。Bogda 侧只等人把专用 worker 的精确 ID 和共享文件路径填进 3101。DEF-03 真 checkpoint 仍要有 worker。

## 恢复雷达

```sh
ssh liuxfs@100.78.158.80
sudo systemctl enable --now orchestra-timer.timer
systemctl is-active orchestra-timer.timer   # 期望 active
```

恢复后下一档 23:30 会再注入四阶段。不要用 `deploy_broker.sh` 的 `ORCHESTRA_ENABLE_TIMERS=0` 现网重装来「恢复」——那会连 backup/exam-watch 一起关掉。

## 未做（仍禁止）

- 改 3100 入口
- Wake Bridge / `dorm-x86`
- 研究 Flow 进 `pi-service`
- 未开口删 `bogda-s2-acceptance-20260901-...`
- 停 broker / exam-watch / backup
