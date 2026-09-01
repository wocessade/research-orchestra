# 系统运行教训库（Lessons Learned）

> 维护协议：**每个 mission 归档时，协调者必须把该 mission 新增的教训提炼追加到本文**（mission completion 固定步骤），并同步检查 CLAUDE.md 锚与 memory 是否需更新。本文是三层知识锚的"体"（CLAUDE.md=锚、memory=个人层）。
> 教训格式：一句话教训 + 场景 + 规则。同类重复出现两次以上的教训升级为红线（进 CLAUDE.md）。

## A. Agent 纪律

1. **并发模式按文件重叠度选**：文件重叠 → 副本隔离+diff 回流（030）；文件完全不重叠 → in-place 并行（032，5 路同改仓库零冲突）。派发前先画所有权矩阵。
2. **验收与执行解耦**：合并/机械操作协调者可亲自做（记 DECISIONS），审查/判断必须派独立 agent。030/031/032 三次验证：独立验收每次都抓到真问题（fidelity 偏差、M-4 无测试证明）。
3. **叶子交付物必须落盘**：关键输出写文件（subtree-report.md），不能只靠回复文本——031 A2 的 5 LOW+2 观察因未落盘催收两次未归。
4. **嵌套叶子的通信**：叶子最终回复文本自动回父代理；SendMessage 对嵌套 agent 不可达（031 三个叶子踩坑）。
5. **派发前排覆盖矩阵**：每个目标文件至少一个叶子负责；验收环节固定做覆盖核对（031 漏掉 test_taskfile.py 被验收 agent 补位）。
6. **严重度标尺根统一**：子树/叶子各自定级偏差实测 22%（031：4 条 MED 降 LOW、codex 的 HIGH 裁定 MED）——最终定级必须由根/验收层按统一标尺重判。
7. **每条 finding 必须有测试证明**：验收对照"finding→修复→测试"逐条映射；无测试的修复记为缺口并当场补（032 M-4）。
8. **后台任务等待用完成通知，禁长 sleep 轮询**：长前台轮询被 harness 误杀（027 互审两次失败）；codex 类长任务 --timeout ≥900。
9. **叶子自首机制**：任务提示词强制"方案偏离必须自首"——032 L4 自首测试方案偏离，避免静默走样。
10. **TDD 先红后绿**：新增测试必须先跑红再修复（032 全部叶子执行；L2 诚实报告一条"本就是绿"的回归守卫型测试）。

## B. 技术坑（平台/工具）

11. **Windows 测试可移植性四件套**：`/bin/bash` 硬编码 → `shutil.which("bash")`；sed/awk 的 RHS 反斜杠被当转义 → 路径 as_posix()；`with sqlite3.connect()` 只 commit 不 close（+引用环延迟关闭）→ 显式 commit+close，Windows 文件锁；msys `kill -0` 不认原生 Windows PID → skipUnless(posix)。
12. **codex CLI 在 GBK 控制台打印崩溃**：调用前设 UTF-8（031 实测）；冷启动 ~2min，真实调用按 1800s 超时规划。
13. **dsh --patch 是整体替换非深合并**：patch 文件必须带完整 config（provider+model），只写 model 会丢 provider（029 实测）。
14. **mock 假绿陷阱**：side_effect 列表直接放函数引用会丢 self 假通过——用 autospec=True + 计数器委托真函数（030 B 探针）。
15. **Cygwin/Git Bash 中文乱码**：需要看中文输出时写文件用 Read 读，不在终端直接 cat。
16. **任务开发按部署目标平台写**：broker/脚本目标=Linux(Pi)，开发机 Windows 适配属测试层问题，勿为适配改生产脚本语义（030/032 界限）。

## C. 合并/工程

17. **同文件双轨改动合并**：外部协作者大提交与本地工作撞车时，人工定原则逐块裁决——实战模式"对方主体 + 保留我方增量 + 我方边界保护（timeout 类）"（a2d31b8）。
18. **声称 vs 实现必须实测核对**：SOL 报告"Skill 未安装"实为已装 unlocked（M-10）；报告内部两处表述还可能互相矛盾（notify 恢复原则 vs §5）——审查时把报告当"声称清单"逐条验证。
19. **文档勘误机制**：发现事实漂移直接在原文勘误（删除线+日期+finding 编号），不另开新文档（M-10 落地方式）。
20. **修复按报告方案执行、不扩大范围**：小包 A 12 条全按方案落地（合计约 30 行），验收逐条比对"实现 vs 方案"——范围纪律是修复质量的一半。

## D. 通信/知识

21. **三层知识锚**：CLAUDE.md（每会话自动加载的锚，2-3 行指针）→ docs（版本化的体，可 push 给协作者）→ memory（个人层 feedback/reference，跨项目召回）。教训先入 docs，高价值高频的再提 CLAUDE.md/memory。
22. **生成内容必须验证源文档事实**：凭记忆概括不可靠（028 haiku 初稿 4 处事实错误被复核修正）；数字/文件名引用必须回源核对。
23. **模型路由纪律**：子代理默认 haiku（最便宜），视觉需求 sonnet，交叉验证 codex；模型调度策略用户自理（fcc-server 勿动）。

## E. 教训升级记录

- 030/031/032 的并发纪律（A1-A10）已固化进 `docs/superpowers/specs/2026-08-20-concurrent-work-modes.md` 与 memory `high_concurrency_modes`。
- codex GBK（B12）已入 memory `codex_windows_console_encoding`。

## F. 033 追加（2026-08-20）

24. **Claude Code `!` 前缀无 TTY**：交互式命令（passwd 等）在 `!` 里跑不了；远程改密的非交互链 = 密钥认证 SSH + `printf '旧密\n' | sudo -S -v` 缓存凭据 + `chpasswd`/`smbpasswd -s`，改完用 `sudo -k && sudo -S -v` 反验新密。
25. **功能重叠裁决模式**：本地交互 skill 与已上线自动化实现重叠时，以"已上线+有验证闭环"的为准（雷达 validator/SHA/at-most-once vs pipeline 交互版），对方独有增量并入计划而非另起炉灶（033 兼容度分析）。
26. **快照型交付物必须带漂移声明**：skill 快照入仓库时 README 写明快照日期+活副本路径+刷新方式（L18 的文档化落地）。

## G. 034 追加（2026-08-20）

27. **Windows `write_text` 换行翻译毁行尾敏感产物**：生成的 ICS 用 `\r\n`，`Path.write_text` 默认 newline 翻译再叠加成 `\r\r\n`，ICAL.js 解析 0 事件（页面"无事件"而 69 个单测全绿）。规则：行尾敏感产物用 `newline=""` 或 write_bytes 写出，且回归测试用**字节级断言**（assertNotIn b"\r\r"）而非文本断言。

28. **测试夹具必须锁真实契约，mock 假绿会掩盖系统级缺陷**：status 夹具按"假设形状" mock `orchestra_last_report={"ts": ...}`，真机契约是 `{"broker": ..., "sync": ...}`——4B 在真机上永远离线而测试全绿。终审读 monitor 源码（写入点）才暴露。规则：跨组件契约的夹具形状必须对照被调方**源码写入点**核实（不是 docstring），终审必须留一次"对照真实上游"的检查。

29. **框架的启动自愈会复活你删掉的文件**：Homepage `checkAndCopyConfig` 在配置缺失时从 skeleton 重建——/MIR 删掉的 widgets.yaml 每次启动复活（stock 磁盘 widget 404）。规则：删框架配置前读其启动逻辑；持久修法=提交空文件（`[]`）占位，而非删除。

30. **subagent 停滞/报错 ≠ 没干活**：两个"失败"的修复代理实际已完成实现并 commit（一个 stall 在报告阶段、一个报 prompt too long 前已落地）。规则：恢复先查 git log + 工作区 diff，账本（.superpowers/sdd/progress.md）是恢复地图；已 commit 的工作绝不重跑。

31. **Windows 计划任务 onlogon 触发器非提权被拒**：schtasks /sc minute 可注册、/sc onlogon 拒绝访问。规则：用户级开机自启落地到用户启动文件夹（%APPDATA%\...\Startup），bat 用 start /min 最小化，无凭据内容可入库。

32. **schtasks 只继承登录时的用户环境快照**：用户环境变量（setx）改后，已在运行的计划任务仍看不到新值，需登出重登才继承——手动 refresh 验证通过但下个 10 分钟 tick 又回到降级。规则：改用户环境变量后验证分两步：①手动跑验证值正确 ②提醒用户重登并等一个 tick 再确认计划任务路径。

## H. 控制台收束（2026-08-20）

33. **Agent 看日程靠结构化字段，不靠刷留言**：个人临近事项进 `status.json.upcoming_personal` + CLAUDE.md 口头提醒协议；refresh 每 10 分钟跑一次，往 `messages.md` 自动追加会刷屏。卡片栏只放需要人拍板的待决/告警。

## I. 控制台/雷达（2026-08-21）

34. **Windows 有 Git Bash ≠ sync_pull 能用**：计划任务找到 bash 后跑 `sync_pull.sh` 常 exit 1，控制台雷达停在旧日。规则：Win32 优先本机 OpenSSH `scp -rq`，`ORCHESTRA_SSH_HOST` 空则默认 `10.77.0.1`（RK3528）；bash 失败不要当作已经拉回。

35. **四阶段任务目录带 `nightly-radar-` 前缀**：真机 `T-20260820-nightly-radar-10-fetch`，不是测试夹具的 `T-20260820-10-fetch`。只认短名时 results 已在本地、日报仍显示 8/19 legacy。规则：扫描正则两种都认；加夹具覆盖真机目录名。

36. **Windows scp 部署脚本必剥 CR**：`inject_daily.sh` 带 CRLF 会 `pipefail\r` exit 2，timer 准点但当晚无雷达。规则：`deploy_broker.sh` 远端 `sed -i 's/\r$//'`；传完用 `file`/`od` 验 LF。

37. **往期日期 API 失败不能拆掉 chips**：`GET /api/radar?date=` 找不到时若返回无 `history`，前端 `renderRadar` 会把 19/20 按钮换成「暂无往期」。规则：`find_radar` 任何分支都带 history；前端用上一份 history 兜底。

38. **serve 进程缓存 glue 模块**：`ui/*.js` 可 Ctrl+F5；`feed_radar.py` 改完必须重启 3100，否则 chips 来自 refresh 的新 JSON、点击走旧 API。

## J. 038 SD 卡对换（2026-08-22）

39. **Allwinner 系换卡捕获必须含首 4MB 引导区**：分区级捕获（sfdisk 存档 + 分区 dd）不含 MBR 与首分区之间的 U-Boot eGON 镜像（核桃派在扇区 16 / offset 8196，魔数 eGON.BT0）——16G 卡恢复后完全无法引导（无 ARP 应答）。树莓派引导固件在 FAT 分区内不受影响。规则：Allwinner 平台换卡 = sfdisk 存档 + 首 4MB 原盘 dd（保留源 MBR 扇区 0）+ 分区级镜像 + 恢复后魔数验证；保险转储首 4MB 到仓库外。

40. **整盘扇区数以 sfdisk 报告为准，勿心算**：心算 62542315520B/512=122153350 扇区，实际 122152960，差 390 扇区——part2 超界被 sfdisk 原子拒绝（label-id/part1 均未写，卡零损伤）。规则：目标分区 size 由 `blockdev --getsz` 或 sfdisk 输出算出，重建后 `sfdisk --verify` + `blockdev --getsz` 双校验卡身份。

41. **broker 209/STDOUT 循环重启 = 日志路径所在盘未挂载**：`StandardOutput=append:/mnt/broker/logs/broker.log`，U 盘物理不在时 systemd 报 `Failed to set up standard output: No such file or directory`（status=209），restart counter 无限累加。排查顺序：lsblk 设备枚举 → dmesg → 物理检查；修复 = mount 后 `systemctl restart`（nofail 的 fstab 挂载启动时被跳过，热插后 systemd 不自动重挂，需手动 mount）。

42. **Persistent timer 补跑 ≠ 注入保证**：4B 换卡关机跨过 23:30 注入窗口，01:45 上电后 timer 补跑，但 broker 还在 209 循环崩溃，注入失败——22 日晨间雷达日报缺失一期。规则：跨关机窗口后验证 timer 补跑产物实际落盘（tasks/ 有任务卡、archive 有归档），不假设补跑成功；发现缺失可手动重跑 nightly-radar 四阶段。

## K. 门禁诚实（2026-08-22）

43. **软 schema / 未接线配置 / 仍被跟踪的 ignored 目录比缺文档更危险**：`jsonschema` 或 `metrics.schema.json` 缺失时若跳过校验，digest 仍显示锁定；`rules.yaml` 从未被 Broker 读取却写得像控制面；`orchestra/results/` 已 gitignore 但仍可能留在索引里（含嵌套 `results/results/`）。规则：结论层校验 fail-closed；配置文件要么有消费代码要么标明人工约定；红线目录 `git ls-files` 交叉检查后 `git rm --cached`。

## L. Bogda 检查点（2026-08-26）

44. **Type-A 完成不能 acquit 科研结论**：命令成功、产物存在、检查点「批准继续」都只推进 Flow；`scientific_status=accepted` 仍只能由人工科研评审写入。规则：不要把检查点批准映射成 accepted；跨模型评语最多当 Artifact 证据。

45. **人拒绝 Type-B 门 = Cancelled，不是 Failed**：伪造系统失败会把「实验不该做」记成基础设施事故。规则：`CheckpointRejected` 返回 Prefect `Cancelled`。

46. **Prefect resume 不要叠 `COMMAND_OUTCOME_MISMATCH` 回读**：pause→Running 是 worker 续跑，控制台回读仍可能看到 Paused。规则：检查点命令做到 allowlist + `command_version` 即可；取消/暂停队列上已有的四层回读不要往新命令上复制。

47. **给 supervised 加暂停会挂死旧的 Type-A 切片**：垂直切片若仍用 supervised 会在 `pause_flow_run` 上等一个永远不来的人。规则：纯执行/产物测试改用 `autonomous` 或测试内自动 resume；shell 没有计划产物就不要暂停 `plan_approval`。

48. **协调器可以开车，不能当陪审团**：`supervised` 协调器可写计划、提实验、耗预算；`wait_for_decision` 留在 Flow 里。模型说「计划已足够 / 结果支持结论」只是 Artifact 内容，不能跳过 Type-B，也不能把 `scientific_status` 写成 `accepted`。未知工具直接拒绝；不在允许列表里的实验类型停在 `experiment_approval`，仍是 `unreviewed`。

## M. RK3528 备机（2026-08-28）

49. **Orchestra 备机禁止 enable 与现网相同的 timer**：`orchestra-timer` / exam-watch 双开会双注入雷达、双告警。规则：并行机 `ORCHESTRA_ENABLE_TIMERS=0`，`api_url` 留空直到一次切；切日清单 `orchestra/docs/rk3528-standby-cutover.md`。
50. **这块 Armbian 没有 nmcli，有 netplan+wpa**：USB MT7601U 用 netplan `wifis` + 电口静态 `/30` never-default。`/tmp` sticky 下 root 不能覆盖 liuxfs 的半截 curl 产物——大文件下到 `/var/tmp`。
51. **切到 RK3528 后文档默认机必须一起改**：Prefect 池名仍叫 `pi-service`，但 SSH/SMB/控制台缺省 host 是 `10.77.0.1` / `rk3528`，不是 4B `192.168.0.250`。venv 的 python 不能指向已搬走的 `/root/.local/share/uv/python`。
52. **从 4B 拷来的 Prefect venv 要修 shebang**：Armbian 上 `uv python` 装到 `/opt/uv-python/...`，否则 unit 报 203/EXEC。

## M2. remount 自愈（2026-08-30）

53. **挂载条件失败不会触发 `Restart=on-failure`**：`ConditionPathIsMountPoint` 不满足时 unit 是 skipped/dead，不是 Failed。USB SSD 掉盘再挂上后，只靠 `WantedBy=multi-user.target` 不会把 Prefect 拉回来。规则：server/worker 必须 `BindsTo=mnt-nas.mount` 且 `WantedBy=mnt-nas.mount`；**health timer 不要绑**。
54. **只换 unit 不要跑整包 `install.sh`**：`--install` 会 `uv sync` 并改 `/etc/bogda/last-backup`。规则：热修两份 service 时手工备份到 `backups/<UTC>/`。
55. **RK3528 SSH 优先 Tailscale**：直连 `10.77.0.1` 可能 `Host key verification failed`，Tailscale `100.78.158.80` / `rk3528` 可用。规则：BatchMode 先试 tailnet；不要默认 `StrictHostKeyChecking=no`。

## N. Gate 7 影子（2026-09-01）

56. **挂账页必须跟验收报告一起改**：关闭 Gate 后若锚页仍写旧红线，下一会话会按过时口径停工。规则：关闭时同步改 `CLAUDE.md`/`README.md`，历史工作台加「已关闭」横幅，不另开第二套现状；也不要用后来的服务恢复改写失败轮原文。
57. **S2 脚本假设会在真 Prefect 上碎**：队列名不全局唯一、Artifact 列表首项不是最新、新建 pool 会多一个 `default` 队列。规则：硬停后从已写入状态续跑，不要重放成功命令；不要把临时驱动的假设做成产品重试框架。

## O. NOW-06 预研究接线（2026-09-02）

58. **四组 exact allowlist 不是单一控制**：只锁 deployment id 时，把生产 deployment 塞进白名单仍会写到 `pi-service`。规则：submit/cancel/review/checkpoint 必须联合校验 `work_pool_name`。
59. **recovery 写入开关必须跟真实 backend 绑定**：allowlisted-test 的 owner 若只因角色打开 `resolve_decision`，Unwired adapter 会把原来的 403 变成 503，并让前端露出假按钮。规则：`recovery_writes_enabled` 仅在配置了 `BOGDA_USAGE_UNKNOWN_DB` 时为真。
60. **`slots=True` 的 frozen dataclass 没有 `__dict__`**：HMAC 凭证复制要用 `dataclasses.replace`，不要 `**obj.__dict__`。
61. **审批库必须成对出现，MAC 不准出 API**：`BOGDA_APPROVAL_DB` 与 `HMAC_KEY` 只配一个就 fail-closed；签发回执不含 mac/nonce，worker 用同一文件 `get_open`/`consume_open`。
