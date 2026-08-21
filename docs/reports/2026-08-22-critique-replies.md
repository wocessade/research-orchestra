# 给 Opus / GPT-SOL 的回复（2026-08-22）

作者：项目 owner 侧（本机 CC 代写，已对照仓库落地）。基线：你们评的是 `39d284a` / `56a84f3`；此后 ingest fail-closed、`academic-shared` 入 digest 契约、`rules.yaml` 标明不读、`orchestra/results` 脱索引，见 `3117b9f` 起。

写法：**先定要什么结果，再决定还改不改过程。**

---

## 共同接受的总判断

Orchestra 是工程质量不错的 **job runner + 夜间雷达**，不是自主科研体。防护以前偏执行层（路径、超时、队列），结论层（metrics）曾经软。文档里手抄测试数/digest/SHA，会变成第二套状态库。这些我们认。

不接受的：改产品名当第三刀；为「唯一事实源」立刻新写一个扫全世界的 `orchestra_check.py`；把 `degradation_order` 接进 dispatcher（降级仍是人手切 Windows dsh）。

---

## 给 Opus

你抓的裂缝是对的：叙事是「科研编排」，担保的是「火车准点」。雷达自动化的是定时+幂等，不是「系统自己判断哪篇重要」。我们把对外 README 改成**科研任务调度器**，不再用自主科研当第一句。

第一刀（防护重心）已按你的修法做了：`jsonschema` / schema 文件缺失 fail-closed；`metrics.schema.json` 作为 required skill `academic-shared` 进 `skills.json`（`contract_files` 不能写 `..`，所以是独立条目而不是 engine 目录内的假相对路径）。**digest 尚未 `--lock-current`**——改完必须人审再锁，否则 ingest HARD。这是故意的，不是漏做。

第二刀（唯一事实源）：同意「Markdown 不准当运行数据库」。做法是删 README 里的测试计数和 mission 流水，运行手册只解释命令。不在这一轮造 `orchestra_check.py`：先让文档停止说谎，再考虑一条命令吐 JSON。锐评可以过期；README 不再承诺永不过期的数字。

第三刀（改名）：产品目录名仍叫 Orchestra，**对外一句话改诚实**。真要自主判断论文/实验，那是研究方向定了之后的研究引擎问题，不是再加一块控制台。

装饰配置：`rules.yaml` 已标明 Broker 不读。`model-routing.json` 继续「人/CC 查表写进任务卡」——这是用户划走的调度权（fcc-server），不是漏接线。

双重 `results/`：已 `git rm --cached`（含 `results/results/`），磁盘 attempt 保留。gitignore 本来就忽略该目录，疤在索引里，现在拿掉了。

---

## 给 GPT-SOL

7/10 和分维我们当工作清单，不当分数崇拜。Broker 内核、雷达阶段化、事故进代码——同意这是该留的资产。

P0 传递依赖：同上，schema 进契约 + fail-closed。P0 验收不可重放：历史报告仍引用 Temp/Pi 日志，**不回溯改写成 evidence bundle**（改历史报告会制造第三套「真相」）。新工作约定：报告只链仓库内路径或可校验 hash；不再把 `D:\Temp` 当验收附件。

P1 装饰控制面：`rules.yaml` 去哑雷（文档）。不接线 `default_executor`。Task 未知字段/重复 key/timeout 范围：**未做**。现网雷达模板与大量 shell 冒烟卡还在用半开放解析；收紧要一次全量 parse 回归，放到部署窗口之后，避免「治理」先把今晚雷达打成 invalid。

P1 原子发布 `releases/<sha>`：**未做**。`deploy_broker.sh` 仍是停服覆盖。真要做需要改 systemd WorkingDirectory 和一次停机窗口；半套 symlink 比现在的逐文件 scp 更危险。

P2 Skill 四档：README/`orchestra/skills/README.md` 用文字分了 runtime-integrated / distribution-only / reference-only，**没有搬目录**。只有 engine + shared schema 进强 digest。

P2 文档反噬：根 README 已砍成现状页。教训库继续只追加，不当第二 changelog。

---

## 下一步（从结果倒推）

**结果 A — 入学后能稳定收雷达、偶发跑实验卡、论文改稿不受基建打扰**

过程：Pi 部署窗口一次做完；digest 人审锁定；3100 继续当本机汇合面；不新开 Skill/控制台大功能。

**结果 B — 结论层数字可被第三人复现**

过程：ingest 已 HARD；接下来是实验卡 `required_outputs` 在真实 EXP 上成为习惯，而不是给所有 shell 冒烟卡强制产物契约。`orchestra_check.py` 若做，只包 unittest + `check_skills --strict` +「gitignore 目录是否仍被跟踪」，不扫历史 Markdown 数字。

**结果 C — 调度重心转到 Hermes（自然语言值班）**

这不是 4B 升级，是**再买/再腾一台常驻盒**。倒推硬件见根 README「若要把调度重心转到 Hermes」：≥8GB、SSD、API-only、不与 2GB Broker 合住、微信仍在 Windows。Hermes **替代不了** Broker；它最多成为写卡/问进度的通道。未进组、方向未定，C 不采购。

**明确不做的过程：** 换产品名、OpenClaw 切换、4B 上 Hermes、原子发布半成品、把两份锐评抄进 CLAUDE 当状态。
