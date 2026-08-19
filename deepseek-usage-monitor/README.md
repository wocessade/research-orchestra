# DeepSeek 用量监控套件

树莓派墨水屏 DeepSeek 用量监控 +（已停用）Windows Claude Code hooks 上报。

| 目录 | 说明 |
|------|------|
| `usage-monitor/` | Pi 端 Flask + 墨水屏 + LED + 用量抓取（主项目） |
| `windows-reporter/` | Windows 端 reporter（**已停用**，仅调试/历史保留） |
| `docs/` | 设计文档与实施计划（历史参考） |

## 快速入口

- 部署与运维：见 [`usage-monitor/README.md`](usage-monitor/README.md)
- Windows 部署到 Pi：在 `usage-monitor/` 下运行 `deploy_to_pi.py`
- Hooks 已停用：勿再改用户 `~/.claude/settings.json`；详见 `windows-reporter/README.md`
- 树莓派 → 核桃派 1B：见 [`docs/walnutpi-1b-migration-guide.md`](docs/walnutpi-1b-migration-guide.md)

## 路径说明

- **仓库（本机）**：`D:/pythonProject/deepseek-usage-monitor/...`
- **树莓派运行目录**（systemd）：仍为 `/home/liuxfs/usage-monitor`（与仓库父目录名无关）
