# dsh 只维护 3101，不改合同

在 RK3528 上用 headless dsh（Flash、短 timeout）时，**唯一允许的运维动作**是：

```sh
sudo -n /opt/bogda-console/maintain.sh status
sudo -n /opt/bogda-console/maintain.sh health
sudo -n /opt/bogda-console/maintain.sh logs
sudo -n /opt/bogda-console/maintain.sh restart
```

禁止：

- 读 `/etc/bogda/console.env` / `bogda.env`
- 改 allowlist、HMAC、Prefect auth
- 把研究 Flow 丢进 `pi-service`
- 动 3100
- 开 `tailscale funnel`
- 常驻会话等人说话

进程由 systemd 保活。dsh 是手脚：看一眼、必要时 restart。挂着不动不打模型请求则不烧 token；本任务仍应干完退出。

人看页面用 MagicDNS：`http://rk3528.tail6d8b09.ts.net:3101/`（裸 Tailscale IP `:3101` 会 404）。
