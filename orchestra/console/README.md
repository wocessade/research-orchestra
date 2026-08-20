# Orchestra 控制台（GUI 汇合面）

以双层日历为核心的只读控制台。**v2 默认入口**：自研浅色静态页 `http://127.0.0.1:3100/`（与 glue 八产物同端口）。Homepage（3000）配置仍保留作兼容回退。

- 设计 spec：`docs/superpowers/specs/2026-08-20-console-design.md`
- v1 计划：`docs/superpowers/plans/2026-08-20-console-v1.md`
- v2 美化任务书：`docs/superpowers/specs/2026-08-20-console-v2-beautify.md`（Grok 已接手并交付）

## 组件

| 路径 | 职责 |
|---|---|
| `ui/` | **v2 展示层**：`index.html` + `styles.css` + `app.js`（浅色、高密度、四页 SPA） |
| `console_feed.py` | CLI：`refresh` 聚合 / `serve` 静态服务（out/ 八产物 + ui/） |
| `feed_schedule.py` | console-schedule.toml → 双 ICS |
| `feed_messages.py` | messages.md 解析（待决/告警） |
| `feed_status.py` | usage-monitor 聚合（降级不报错） |
| `feed_radar.py` | results/.research 扫描 |
| `feed_serve.py` | out/ + ui/ 同端口服务；messages.json mtime 热重 |
| `homepage/` | v1 Homepage 配置（保留，不删除） |
| `startup_serve.bat` / `startup_homepage.bat` | 开机自启 |
| `out/` | 产物（不入库） |
| `tests/` | unittest（69） |

## 使用（v2）

1. 刷新数据：`python console_feed.py refresh`（计划任务 OrchestraConsoleRefresh 每 10 分钟）
2. 起服务：`python console_feed.py serve` → **打开 http://127.0.0.1:3100/**
3. 四页：今天 / 雷达 / 任务实验 / 系统（顶栏切换；URL hash `#today|#radar|#tasks|#system`）
4. 留言：写 `messages.md` → 页内约 5s 热重可见
5. 环境变量（绝不入库）：`ORCHESTRA_MONITOR_TOKEN`、`ORCHESTRA_MONITOR_API`、`ORCHESTRA_SSH_HOST`

### Homepage 回退（可选）

仍可用 `start_homepage.bat` 起 3000；配置在 `homepage/`。v2 主路径不再依赖 Homepage。若重启 Homepage，确认 `D:\Apps\homepage\config\widgets.yaml` 内容为 `[]`。

## 视觉约定（v2）

- 强制浅色阅读底（`color-scheme: light`），深墨字 / 浅底，不混用深底黑字
- 字号四档：品牌标题 / 区块标题 / 正文 / 时间·数据（IBM Plex Sans + Mono）
- 系统层事件蓝、个人层绿；待决红、告警琥珀
- 信息密度优先：无卡片套卡片拉伸；空数据列不制造假高度

## 降级语义

usage-monitor 不可达 / token 未配 → 顶栏降级条 + 设备离线，其余本地缓存继续展示；sync_pull 跳过 → 雷达/attempt 沿用旧数据；ICS 失败 → 沿用上次产物 + 自动告警留言。

## 验收截图

前后对比：`D:\Temp\console-acceptance-v2\before\` 与 `after\`（01-today / 02-radar / 03-tasks / 04-system）。
