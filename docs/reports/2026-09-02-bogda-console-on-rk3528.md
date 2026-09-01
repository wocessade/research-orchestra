# Bogda Console 3101 上 RK3528

日期：2026-09-02  
授权：owner 同意把 3101 放到盒子上，由那边的 dsh 维护。

**不是 3100 切换。不是 funnel。不是研究进 `pi-service`。不是用 dsh 代替 systemd。**

## 合同

| 项 | 值 |
|---|---|
| 进程 | `bogda-console.service`，User `bogda`，代码 `/opt/bogda-console`（eMMC） |
| 监听 | `127.0.0.1:3101` |
| Tailnet | `tailscale serve --bg --http=3101 3101` → `http://100.78.158.80:3101/` |
| 首发 profile | `real-readonly` + `observer`（tailnet 上无 HTTP 登录，先只读） |
| Prefect | `http://127.0.0.1:4200/api`，auth 从 `/etc/bogda/bogda.env` 拷进 `/etc/bogda/console.env` |
| USB | 不 `BindsTo=mnt-nas` |
| 保活 | systemd `Restart=on-failure` |
| dsh | 只跑 `/opt/bogda-console/maintain.sh status\|logs\|restart\|health`，干完退出 |

写入（allowlisted-test + 精确 pool ID）等 runner 握手后再改 `console.env`。

## 部署

本机构建 `bogda-console/frontend/dist`，然后：

```sh
ORCHESTRA_SSH_HOST=100.78.158.80 bash bogda/deploy/console/deploy_console.sh
```

不要走 Prefect `install.sh`。

## dsh 维护

见 `bogda/deploy/console/dsh-maintain.md`。挂着不动且不再请求模型则不烧 token；仍不要把 dsh 7×24 挂着当守护进程。
