# CLAUDE.md — Research Orchestra 项目（D:\pythonProject）

## 这是什么

方向无关的科研生产力系统：CC（编排大脑）+ 树莓派 4B Broker（7×24 任务代理，dsh/shell 执行）+ 核桃派（墨水屏展示/异地冷备）+ Codex 副脑（交叉验证）+ Tailscale 三端组网 + 4B 兼职 NAS + 夜间文献雷达（23:30 自动）。

## 新会话接手规则（重要）

接到本项目任何任务前，先读：
1. `orchestra/README.md` — 系统运行手册（命令/链路/运维）
2. `docs/superpowers/specs/2026-08-18-research-orchestra-design.md` §13 — 总 spec 检查清单与各子系统状态
3. `README.md` — 项目全景记录（第三方审查版：决策链、时间线、索引）

按任务范围再读对应 mission 档案：`.tasks/completed/NNN_*`（MISSION/STATE/DECISIONS/BRIEF/AUDIT，编号见目录）。

## 硬约束（红线）

- commit 不加 Co-Authored-By/署名行
- ~/.codex 残留只读；auth.json 绝不 copy/commit/打印内容
- 模型调度策略用户自理（fcc-server 管理端勿动）
- 删除/清理文件前必须先问用户
- 临时文件统一 D:\Temp，不进仓库
- 未跟踪目录（01thesis/、ml-notes/、FCC 脚本、.tasks/、pm3-mcp-server/、.proxmark3/、orchestra/results、logs）一律不入库
- GitHub 仓库 wocessade/research-orchestra 为 private；push 走已配置的 git 代理
- 凭据走环境变量/systemd env，绝不入库

## 关键链路速查

- 派任务：T-*.md 任务卡 → `orchestra/scripts/sync_push.sh` → 4B broker 队列执行 → attempt-N 落盘
- 状态：4B reporter 每 30s POST 核桃派 usage-monitor（X-Monitor-Token 鉴权）→ 墨水屏融合面板
- 雷达：每晚 23:30 自动注入（模板 `orchestra/templates/nightly-radar.md`），晨间 QQ 邮箱日报
- 定时：03:00 冷备到核桃派 / 04:17 NAS 盘内备份 / 周日 04:00 housekeeping
- 双 agent：`orchestra/scripts/codex_exec.py` + `codex_modes.py`（互审/双实现/claim 核验）；本机 codex 冷启动 ~2min，互审建议 --timeout ≥900
- 模型路由：任务卡 `model: flash|pro` 字段（dsh --patch）；codex 三档由 CC 查 `orchestra/config/model-routing.json` 透传
- 测试：broker 41 unittest / scripts 124（discover 从各自目录跑）

## 当前挂账（更新日期 2026-08-20）

- executor.py 3 条 codex 审出 finding 待修（需 Pi 部署窗口）
- 入学前（2026-09）：弱密码整改（见 `orchestra/docs/school-network-switch.md`）、宿舍-实验室互通实测、Tailscale 切换
- 雷达→Zotero 直连方向已提出，待用户拍板（`docs/superpowers/plans/2026-08-20-radar-digest-reading-note.md`）
- 双 agent 想法池剩余项（resume 脚本化 / usage 统计）待选（模型路由表已落地，spec `docs/superpowers/specs/2026-08-20-model-routing-design.md`）
- 待用户拍板：SD 旧副本删除、512G SSD 用途、宿舍 NAS、QQ bot
