# 统一模型路由表设计（subsystem-5 前置项）

> 日期：2026-08-20 ｜ 状态：设计定稿（用户 2026-08-20 确认）｜ 落地：mission 029
> 来源：用户发起讨论（codex/dsh 模型问题）→ 头脑风暴收敛 → 本文档定稿

## 1. Goal

一张用户维护、系统只读的路由表，统一回答"这类任务用什么模型"：dsh（Pi 侧 DeepSeek）按任务选 flash/pro；codex（Windows 侧 OpenAI）按任务选 Luna/Terra/Sol 三档 + effort。CC 是唯一查表者。

## 2. 背景与已定决策（讨论记录）

- **表格式 JSON**（机器读优先；总 spec §8 原 md 表述同步改为 json 路径）
- **生效链路：写卡时填死**——CC 写任务卡时查表把 `model:` 写进卡头；改表只影响下一张卡；Pi 侧不知道表的存在
- **usage 归因账本：不做**（用户决定；用量看 usage-monitor 现有数据）
- **dsh 并发：不改造**——Pi 定位 = 长程单任务监管 + 夜间雷达（排队形式，dispatcher 串行不变）
- **雷达 vs 长实验时序冲突：不加新机制**（不加 priority/deadline 字段）；改以运维纪律兜底：长实验任务卡 **timeout 必须显式设置**（防堵队列）
- **GPT-5.6 三档映射**（2026-07-09 发布；数据源见 §6）：
  - Terra = 默认档（"GPT-5.5 水准、Sol 四成价"，实务主力）
  - Sol = 关键场景专用（complex-audit 哨兵级大审计 effort=high、验收争议裁决）——"关键的地方才用"
  - Luna = 干杂活（批量摘要/雷达总结/视觉快查）；**用户确认 Luna 带视觉**；长文档不喂 Luna（长文本召回弱，MRCR 41.3%）
- **production-fix 不派 codex**：SWE-Bench Pro 上 Claude 80.0% vs Sol 64.6%，真实代码库修复归 CC（owner: claude）
- **Plus 未购买前不做 codex 真实调用测试**（用户约束）；`--model` 具体值（如 `gpt-5.6-terra`）以购买后 `codex /model` 列表为准

## 3. 路由表 Schema（定稿）

文件：`orchestra/config/model-routing.json`（用户维护、系统只读）

```json
{
  "dsh": { "radar-scoring": "flash", "experiment": "pro" },
  "codex": {
    "default": "terra",
    "batch-summarize": "luna",
    "radar-summary": "luna",
    "vision-quick": "luna",
    "mutual-review": "terra",
    "claim-check": "terra",
    "docs-draft": "terra",
    "dual-implement": "terra",
    "complex-audit": { "model": "sol", "effort": "high" },
    "production-fix": { "owner": "claude" }
  }
}
```

约定：
- 值为抽象档位键（flash/pro/luna/terra/sol），不写死完整模型名——具体模型名/端点只在执行侧（Pi patch 文件 / codex 配置），改模型不改表
- `default` 兜底未列出的任务类型；`owner: claude` 表示不派 codex，由 CC（Claude）执行
- 表只增不删字段（向后兼容）；CC 读表容错（缺字段回退 default）

## 4. 消费链 A：dsh（Pi 侧）

链路：CC 写任务卡（查表填 `model:` 头字段）→ taskfile.py 解析入 TaskSpec → executor.py 映射为 `--patch` 覆盖层 → dsh 执行。

改动清单：
- `orchestra/config/model-routing.json`：新建（骨架 + 上述初值）
- `orchestra/broker/taskfile.py`：TaskSpec 增 `model: Optional[str]`，解析 `model:` 头字段（可选、缺省 None；值**透传不校验**——档位校验责任在写卡的 CC，表是唯一真源）
- `orchestra/broker/executor.py`：`model=None` 时沿用现行为；否则追加 `--patch /mnt/broker/dsh-patches/{model}.yml`，且 **patch 文件不存在时任务 failed + 明确错误信息**（防拼写错误静默用错模型）
- Pi 侧：新建 `dsh-patches/flash.yml` / `pro.yml`（**Task 0 先调研 dsh 0.1.0-rc.7 的 profile/patch 结构**——`dsh --dump-config` 输出为准；patch 内容只改 provider 模型字段）
- 总 spec §8 同步：策略表路径 `.md` → `.json` + 系统只读约定一句
- 文档同步：CLAUDE.md 挂账划掉"路由表待办"、orchestra/README.md 补路由表一节（若 026 后已有则只补引用）
- 测试：taskfile/executor 单测（mock 子进程断言 argv 含 --patch；patch 缺失路径断言 failed），broker 41 → 43+

验收：Pi 部署后一次 **flash 真实任务冒烟**（雷达评分任务用 flash 跑通，验证 patch 生效，产出落 attempt-N）。

## 5. 消费链 B：codex（Windows 侧，零代码）

链路：CC 调用 codex_exec/codex_modes 前查表 → 传 `--model`（透传已支持）+ effort 提示词级生效（codex 侧 effort 档位若 CLI 支持则用参数，否则仅在 prompt 中注明）。

约定：
- 零代码改动——查表动作由 CC 在编排时完成
- Plus 购买前：不做任何真实调用验证；**effort 不传**（complex-audit 的 effort=high 实现方式待 Plus 后实测：CLI 参数可用则用参数，否则 prompt 注明）
- 购买后实测项：① `codex /model` 列表确认三档模型名 ② `--model` 传参格式 ③ Luna 视觉传入（`codex exec -i` 图片）——以实际可用性为准更新表值
- 首次实测后把「模型名映射」记回本 spec 附录

## 6. 数据依据（2026-08-20 检索）

- GPT-5.6 三档：Luna $0.20/$1.20、Terra $2/$12、Sol $5/$30（每 1M tokens 输入/输出）；7/30 降价后 Terra 为 Sol 四成价、Luna 再降 80%；三款共享 1.05M 上下文/128K 输出；effort 六档
- 订阅：Free/Go 仅 Codex 内 Terra；Plus $20/月解锁三档自由选
- 基准：Sol 智能体综合第一（Agents' Last Exam 53.6 vs Claude Fable 5 40.5）；SWE-Bench Pro Claude 80.0% vs Sol 64.6%
- 来源：OpenAI 官方 GPT-5.6 页；Vellum/Artificial Analysis 汇总（arte.itlibra.com 解读 2026-07-10；OpenAI API 价格 2026 各站点一致）

## 7. Out of Scope

- usage 归因账本（用户决定不做）
- broker 执行时查表（写卡填死即可，Pi 零依赖表）
- shell 任务的 model 字段（shell 即用户自管脚本，无意义）
- dsh 并发改造（Pi 定位不变）
- 高并发工作模式约定（用户设想另议，未定稿）

## 8. 开放项

- Plus 购买（用户）→ 解锁 §5 实测三项
- radar-summary/vision-quick 首次真实调用后复核档位是否合适（用户可随时改表）
