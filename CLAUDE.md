# CLAUDE.md — Research Orchestra 项目（D:\pythonProject）

## 这是什么

方向无关的科研生产力系统：CC（编排大脑）+ 树莓派 4B Broker（7×24 任务代理，dsh/shell 执行）+ 核桃派（墨水屏展示/异地冷备）+ Codex 副脑（交叉验证）+ Tailscale 三端组网 + 4B 兼职 NAS + 夜间文献雷达（23:30 自动）。

## 新会话接手规则（重要）

接到本项目任何任务前，先读：
1. `orchestra/README.md` — 系统运行手册（命令/链路/运维）
2. `docs/superpowers/specs/2026-08-18-research-orchestra-design.md` §13 — 总 spec 检查清单与各子系统状态
3. `README.md` — 项目全景记录（第三方审查版：决策链、时间线、索引）
4. `docs/lessons-learned.md` — 系统运行教训库（**每个 mission 归档时必须把新教训追加进去**）

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
- 雷达：每晚 23:30 注入四阶段任务（`templates/nightly-radar-{fetch,rank,render,notify}.md` → 10/20/30/40，depends_on 串联），晨间 QQ 邮箱日报；评分五维为唯一权威（pipeline 六维弃用，仅精读/归档场景调用）；日报 top5 精读走 nature-reader
- 定时：03:00 冷备到核桃派 / 04:17 NAS 盘内备份 / 周日 04:00 housekeeping
- 双 agent：`orchestra/scripts/codex_exec.py` + `codex_modes.py`（互审/双实现/claim 核验）；本机 codex 冷启动 ~2min，互审建议 --timeout ≥900
- 模型路由：任务卡 `model: flash|pro` 字段（dsh --patch）；codex 三档由 CC 查 `orchestra/config/model-routing.json` 透传
- 并发两档：标准档（4-8 路扁平，030 已实战）/ 树状档（2 层×≤3 子树×≤12 叶子，031 首跑）；opus 只接口+统一 commit，agent 不 commit；约定 `docs/superpowers/specs/2026-08-20-concurrent-work-modes.md`
- 测试：broker 102 unittest / scripts 154（discover 从各自目录跑；Windows 上 3 个平台正当 skip）

## 当前挂账（更新日期 2026-08-20）

- **阶段定位（用户定调）**：整体工程进入收尾复核；【术】已足够，转入【道】——新任务优先产出论文/研究实体，纯基建项只记挂账不急着做
- SOL 重构 + 030 修复已合并入库（a2d31b8）：四阶段雷达、artifact 校验、taskkill 树杀等需一次 Pi 部署窗口；**skills.json digest 已锁定（2026-08-20，用户审查后 --lock-current --strict，ingest 门禁放行）**——skill 改动后需重新审查+锁定，流程见 orchestra/skills/README.md
- 031 树状档首跑产出 SOL 终审报告（docs/reports/2026-08-sol-refactor-review.md）：**小包 A 已修复入库（739fdfd，1 HIGH+12 MED 全落地，broker 116/scripts 161 绿）**；挂账 B（Pi 部署验证）并入部署窗口
- 入学前（2026-09）：宿舍-实验室互通实测、Tailscale 切换；弱密码整改 4B 已完成（2026-08-20），核桃派 pi 密码待上线后同步
- 雷达→Zotero 直连**推迟到 9.8 开学后再设计**（方向已记 `docs/superpowers/plans/2026-08-20-radar-digest-reading-note.md`）
- 双 agent 想法池剩余项（resume 脚本化 / usage 统计）待选（模型路由表已落地，spec `docs/superpowers/specs/2026-08-20-model-routing-design.md`）
- **GUI 控制台 v1 已上线（mission 034，43fd3a4 已 push）**：Homepage 127.0.0.1:3000 四页 + glue `orchestra/console/`（69 测试绿，Pi 零改动）；refresh 每 10 分钟 schtasks + serve/Homepage 启动文件夹自启；留言=CC 写 `orchestra/console/messages.md`；v1.5（tailnet 手机访问+Homepage 鉴权门）/v2（事件点击派任务、推送、实验 DDL 扫描、pending 卡明细）挂账；**上线后首次真实运行需留意 ORCHESTRA_MONITOR_TOKEN 是否在 schtasks 环境可见**（无 token 则 4B 区降级显示离线）
- 待用户拍板：SD 旧副本删除、512G SSD 用途、宿舍 NAS、QQ bot
