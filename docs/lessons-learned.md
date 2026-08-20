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
