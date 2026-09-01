# Bogda Console 3101 上 RK3528

日期：2026-09-02  
授权：owner 同意把 3101 放到盒子上，由那边的 dsh 维护。

**不是 3100 切换。不是 funnel。不是研究进 `pi-service`。不是用 dsh 代替 systemd。**

## 合同

| 项 | 值 |
|---|---|
| 进程 | `bogda-console.service`，User `bogda`，代码 `/opt/bogda-console`（eMMC） |
| 监听 | `127.0.0.1:3101` |
| Tailnet | `tailscale serve --bg --http=3101 3101` → **MagicDNS** `http://rk3528.tail6d8b09.ts.net:3101/` |
| 首发 profile | `real-readonly` + `observer`（tailnet 上无 HTTP 登录，先只读） |
| Prefect | `http://127.0.0.1:4200/api`，auth 从 `/etc/bogda/bogda.env` 拷进 `/etc/bogda/console.env` |
| USB | 不 `BindsTo=mnt-nas` |
| 保活 | systemd `Restart=on-failure` |
| dsh | 只跑 `maintain.sh` 四动词；`health` 探 `/` + `/assets` + `/api/v1/capabilities`；`restart` 等到 200 |

`http://100.78.158.80:3101/` 会 404：`tailscale serve` 按 MagicDNS 主机名代理，不要用裸 IP 当入口。

写入（allowlisted-test + 精确 pool ID）等 runner 握手后再改 `console.env`。

## 现网（2026-09-02）

- `bogda-console.service` **active**；python 听 `127.0.0.1:3101`；rss ~85MB；盒子当时 available ~3.2Gi
- 盒内 `maintain.sh health` → `http_code=200`
- MagicDNS `/` → 200，SPA 标题 Bogda Console，侧栏「3101 影子运行」，profile 文案 `real-readonly`
- 总览读到 Prefect 项目 `bogda-main`、run `enigmatic-woodlouse`；自主模式控件禁用；电源卡仍是 fixture 模拟/陈旧（`MockPowerAdapter`）
- 冷启动约 12s（import Prefect）。缺 `fixtures/normal-active.json` 会 crash loop，部署脚本现已 fail-closed

## 部署

本机构建 `bogda-console/frontend/dist`，然后：

```sh
ORCHESTRA_SSH_HOST=100.78.158.80 bash bogda/deploy/console/deploy_console.sh
```

Git Bash 用 `E:\Git\bin\bash.exe`。不要走 Prefect `install.sh`。不要 `move_agent_to_root` 到这个 worktree（会试图 `git checkout main`，而 `main` 已占用 `D:\pythonProject`）。

## dsh 维护

见 `bogda/deploy/console/dsh-maintain.md`。挂着不动且不再请求模型则不烧 token；仍不要把 dsh 7×24 挂着当守护进程。

## 聊天框连 worker dsh（2026-09-02 决定：不做）

目标「不用填单那台 Windows 也能审批、把项目推一步」成立，但 **不要**在 3101 上挂一个连着 worker dsh 的聊天框。

| 想做的事 | 正确落点 | 为什么不走聊天→dsh |
|---|---|---|
| 批准暂停 / >20 CNY / checkpoint | 3101 已有结构化按钮（要 `allowlisted-test` + `owner` + runner 精确白名单） | 自由文本会绕过机械白名单 |
| 问「现在卡在哪」 | 3101 总览/运行详情 + 简报 Artifact | dsh 聊天看不到 Prefect 权威状态 |
| 短摘要、失败译成人话 | 盒子 **Prefect 入队** → `pi-service` 拉一次 Flash dsh → 退出（intent `brief`） | 不是 3101 WebSocket 常驻会话 |
| 配环境 / 复现 / 长思考 | **runner 开机后** 的 runner dsh | 盒子 4GB，且 runner 尚未接池 |
| 文件到计算端 | git+commit、runner 已暂存路径、或 NAS `/mnt/nas/.bogda/inbox/<run_id>/`（≤8MiB/文件） | `D:\` 直连、本机 skill 树、聊天里贴 PDF 都不通 |

目录由 `bogda/deploy/shared/prepare_runner_share.sh` 创建。3101 仍不 `BindsTo` USB NAS。

文件直连 worker 的缺口不是聊天能补的：填单机关机后，PDF/skill/`D:\` 本来就不在盒子上。要离机继续，材料必须事先变成计算端可解析引用（见 [`2026-08-30-bogda-runner-dsh-design.md`](../superpowers/specs/2026-08-30-bogda-runner-dsh-design.md) §5.3）。runner 没开机时只能做控制面批准和盒子轻任务，不能假装实验还在跑。

下一跳仍是握手文档里的白名单 + 共享文件，不是 IM。

