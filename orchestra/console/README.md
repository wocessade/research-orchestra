# Orchestra 控制台（GUI 汇合面）

以双层日历为核心的只读控制台。**v2 默认入口**：自研浅色静态页 `http://127.0.0.1:3100/`（与 glue 八产物同端口）。Homepage（3000）配置仍保留作兼容回退。

- 设计 spec：`docs/superpowers/specs/2026-08-20-console-design.md`
- v1 计划：`docs/superpowers/plans/2026-08-20-console-v1.md`
- v2 美化任务书：`docs/superpowers/specs/2026-08-20-console-v2-beautify.md`（Grok 已交付；SOL 从 §0 接手复审，勿从 Homepage 重做）

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
| `tests/` | unittest |

## 使用（v2）

1. 刷新数据：`python console_feed.py refresh`（计划任务 OrchestraConsoleRefresh 每 10 分钟）
2. 起服务：`python console_feed.py serve` → **打开 http://127.0.0.1:3100/**
3. 四页：今天 / 雷达 / 任务实验 / 系统（顶栏切换；URL hash `#today|#radar|#tasks|#system`）
4. 留言：写 `messages.md` → 页内约 5s 热重可见。协议见下方「Agent / CC 协议」
5. **个人日程**：首页可增删改、勾完成、勾「每周重复」、右侧月历跳转；写入 `console-schedule.toml` 的 `[[personal]]`，系统层只读
6. 环境变量（绝不入库）：`ORCHESTRA_MONITOR_TOKEN`、`ORCHESTRA_MONITOR_API`、`ORCHESTRA_SSH_HOST`

## Agent / CC 协议

控制台不是 Homepage 配置玩具，agent 应直接用：

- 打开 `http://127.0.0.1:3100/` 看四页；hash `#today|#radar|#tasks|#system`
- **留言 / 待决 / 告警**：只写本目录 `messages.md`（入库）。格式必须是：

```markdown
## 2026-08-21 08:00 — 雷达日报已出
top5 中 2 篇与方向相关
- 待决：SD 旧副本是否删除？
- 告警：usage-monitor 不可达
```

同一条里可以有多条 `- 待决：` / `- 告警：`，都会进对应栏（待决最多展示 24 条）。标题时间用 `YYYY-MM-DD HH:MM`，破折号是 `—`。删行即撤卡。CLAUDE.md 挂账是权威待办，这里只记增量。
- **个人日程**：走 UI，或编辑 `console-schedule.toml` 的 `[[personal]]` 后 `python console_feed.py refresh`。不要改 `[system]`，那是 4B timer 镜像。
- **临近提醒**：`status.json` 的 `upcoming_personal` 是未来 14 天未完成个人事项。Agent 会话开头/收束口头提醒（48h 内必提）；控制台顶栏绿/橙/红条同步展示。不要用 refresh 往 messages.md 刷提醒。
- **雷达往期**：点「往期日报」chips，或 `GET /api/radar?date=YYYY-MM-DD`。
- 不要往 `out/` 手写 JSON；refresh / serve 热重才是权威生成路径。

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
