# Confirmed Contribution

```yaml
user_confirmed: true    # 用户 2026-09-11 夜间总指令授权自主完成论文（"此任务为最高权限…其余自行处理"）
confirmed_at: 2026-09-11
venue_type: journal
page_budget: null       # 中文期刊小论文，正文约 6000 字
discipline: cs
```

## Research question (one sentence)

仅凭服务端 token 计量记录（缓存命中/未命中字段），能否事后判定两次生成是否复用了同一上下文，从而为 AI 内容来源审计提供独立于文件元数据的证据通道？

## Contributions (1–3; claim-first)

| ID | Contribution (what is new) | Evidence plan (exp / proof / system) | Status |
|----|----------------------------|--------------------------------------|--------|
| C1 | 提出"计量取证"路径并给出可量化判定规则：以 usage 记录中 cache_hit_tokens 为唯一信号，判定"两次生成是否复用同一上下文"，在受控实验中同源/异源完全可分（512 vs 0） | 通道B 裸 API 8 次受控调用（真实平台、真实计费） | verified |
| C2 | 首次实证揭示"通道依赖性"：同一账号、同一平台、同一文本，agent 编排通道（17 次受控调用）因系统提示嵌入每次唯一运行时路径而结构性丧失该信号（17/17 命中为 0）；审计可用性取决于调用链路设计，并给出机制证据（harness 请求日志） | 通道A dsh 17 次受控调用 + 会话日志机制分析 | verified |
| C3 | 面向《人工智能生成合成内容标识办法》核验要求的适用性分析：计量取证可作为隐式标识的独立旁证，但受"跨模型缓存命名空间"限制（跨层级复用不可见），且构成新的复用行为可观测面（隐私双刃） | 通道B 跨层级对照 + 政策文本对照分析 | verified |

## Non-goals (explicitly out of scope)

- 不做 AIGC 文本检测（"是否 AI 生成"）——本文审的是"来源与传播"，不是"生成与否"。
- 不做跨租户攻击（时序侧信道偷取他人提示），也不评估攻击成功率。
- 不覆盖多平台/多厂商泛化结论（本文仅一处平台、单账号）。

## User confirmation log

- [x] 用户下达夜间总指令，明确要求：以 bogda 执行研究、产出与其专业（AI 安全×内容治理）相关且不重复的可投稿论文、academic-journal 出 LaTeX+PDF；授权自主决策（用户睡眠中）
- [x] 无空/含糊贡献行（均为 claim-first，且各有实验证据）
