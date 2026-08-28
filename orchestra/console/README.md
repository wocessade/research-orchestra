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
| `startup_serve.pyw` / `startup_homepage.pyw` | 开机自启（.pyw 无窗口；Startup 里不要放 .bat，会闪 cmd 黑框） |
| `out/` | 产物（不入库） |
| `tests/` | unittest |

## 使用（v2）

1. 刷新数据：`python console_feed.py refresh`（计划任务 OrchestraConsoleRefresh 每 10 分钟）
2. 起服务：`python console_feed.py serve` → **打开 http://127.0.0.1:3100/**
3. 四页：今天 / 雷达 / 任务实验 / 系统（顶栏切换；URL hash `#today|#radar|#tasks|#system`）
4. 待决：首页输入框回车写入（`POST /api/pending`），红叉删除。告警/最新由 refresh 派生，不必手写。协议见下方。
5. **个人日程**：首页只列今天起的个人卡片。点月历某天打开添加栏（写完回车 / 失焦 /「添加」）；卡片上可改日期和时间；完成圈与红X删除；可拖到另一天。写入 `console-schedule.toml` 的 `[[personal]]`。系统定时只在「系统」页。
6. 环境变量（绝不入库）：`ORCHESTRA_MONITOR_TOKEN`、`ORCHESTRA_MONITOR_API`；`ORCHESTRA_SSH_HOST` 缺省 `10.77.0.1`
7. **雷达往期**：点日期 chips 切换；`GET /api/radar?date=YYYY-MM-DD` 必须带 `history`，chips 不能随切换被清空。
8. **任务实验**：排队/运行中/完成/挂起/实验卡每种最多展示 10 条。

## 近期维护（2026-08-21）

首页日程与雷达同步的实装记录，给后续会话接手用。

| 项 | 说明 |
|---|---|
| 个人日程 UI | `ui/app.js` `renderAgenda`：个人卡片 + `PUT /api/personal`；系统 ICS 仍生成，首页不展示 |
| 添加入口 | 今天组自带「写点什么」；其它天要点右侧月历；提交=回车/失焦/添加按钮 |
| Windows sync_pull | `console_feed.sync_pull`：Win32 **优先 OpenSSH scp**，缺省 host `10.77.0.1`。Git Bash `sync_pull.sh` 在计划任务里常 exit 1，不要当唯一路径 |
| 四阶段目录名 | 真机是 `T-YYYYMMDD-nightly-radar-{10-fetch,20-rank,30-render,40-notify}`；测试夹具还有短名 `T-YYYYMMDD-10-fetch`。`feed_radar._DIR` 两种都认 |
| 昨晚补跑 | Pi：`ORCHESTRA_DATE=20260820 bash /home/liuxfs/broker/inject_daily.sh`。邮件走 40-notify，控制台要等 scp + `find_radar` 认目录 |
| CRLF | Windows scp 脚本会带 CR。`deploy_broker.sh` 传完 `sed -i 's/\r$//'`；`inject_daily.sh` 遇 `pipefail\r` 会 exit 2、当晚无雷达 |
| glue 热更 | `ui/` 静态文件随请求更新（Ctrl+F5）；`feed_radar.py` 被 serve **import 缓存**，改扫描逻辑必须重启 3100（pythonw / `startup_serve.pyw`） |
| 往期 chips | 查不到该日时 API 仍返回 `history`；前端用上一份 history 兜底，避免按钮消失 |

补数据：`py -3 orchestra/console/console_feed.py refresh`（会 scp results）。只重建 JSON：`refresh --no-sync`。

## Agent / CC 协议

控制台不是 Homepage 配置玩具，agent 应直接用：

- 打开 `http://127.0.0.1:3100/` 看四页；hash `#today|#radar|#tasks|#system`
- **留言 / 待决 / 告警**：`GET /messages.json` = `messages.md` 人工条 + refresh 派生条。
  - 告警/最新：glue 从 `status.json` / `radar.json` / `sync_note` 生成（离线、未鉴权、同步失败、雷达阶段失败、attempt failed、雷达摘要）。不要把这些再手抄进 md。
  - 待决：首页输入框，或写 `- 待决：`。待决最多展示 24 条。标题时间用 `YYYY-MM-DD HH:MM`，破折号是 `—`。删行或红叉即撤卡。CLAUDE.md 挂账是权威待办，这里只记要 owner 拍板的增量。
- **个人日程**：走首页任务卡片，或编辑 `console-schedule.toml` 的 `[[personal]]` 后 `python console_feed.py refresh`。不要改 `[system]`，那是 RK3528 timer 镜像。
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
