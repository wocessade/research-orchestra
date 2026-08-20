# Academic Coursework Pipeline

课程论文（大作业）从选题到提交的完整编排 —— Claude Code 全流程编排器。路由器 + manifest + 按需加载的分块架构（上下文缩减 70-80%）。

## 入口

| 入口 | 适用场景 | 起点 |
|------|---------|------|
| **Course-Assignment (全自动)** | 课程大作业，有详细要求 | C1 → C2 → C3 → C4 → C5 |
| **Course-Assignment (半自动)** | 课程大作业，需用户参与决策 | C1 → C2 → C3 → C4 → C5 |
| **Existing-Manuscript** | 已有完整初稿的课程论文 | QC4 gate → C5 |

## 快速开始

```
用户: "帮我写一篇关于X的课程论文"
Claude: [路由器读取 manifest → 加载 static/core/ 规则 → 按需加载 strategists/C1-strategist.md]
  → 选题头脑风暴 → 文献检索 → 写作(.docx) → 六维审查 → 修订收敛
```

## 做的事情

- **选题与论点定义**：头脑风暴候选选题，定义 3+ 核心论点及其逻辑关系
- **文献检索**：中英文多数据库检索 + 质量评分 + 引文滚雪球 + 引用网络分析
- **完整 .docx 写作**：标题、摘要、正文（3+ 论点章节）、结论、参考文献、AI 使用声明
- **六维审查**：内容、结构、AI 语感、格式、逻辑、事实准确性
- **修订收敛**：多轮修复 + 回归检测，硬上限 3 轮
- **注水（可选）**：控制性扩写 + De-AI 检测 + 查重预检

## 依赖清单

### 内嵌 Skill 参考（skills-embedded/）

流水线已将所有外部 skill 内容打包为本地快照（`skills-embedded/`），无需额外安装。

**核心：**

| 文件 | 用在 |
|------|------|
| `skills-embedded/scientific-brainstorming.md` | C1: 选题头脑风暴 |
| `skills-embedded/paper-lookup.md` | C2: 多数据库文献检索 |
| `skills-embedded/markdown-mermaid-writing.md` | C3: Mermaid 图表辅助 |
| `skills-embedded/docx.md` | C3: python-docx 操作参考 |
| `skills-embedded/pdf.md` | C2, C4: PDF 文献阅读 |
| `skills-embedded/generate-image.md` | C3: AI 图片生成（可选）|
| `skills-embedded/latex-thesis-zh.md` | C3: 中文 LaTeX 模板参考（可选）|

### 外部软件

| 软件 | 用途 | 安装 |
|------|------|------|
| **Python 3.8+** | python-docx 生成 Word 文档 | `pip install python-docx` |
| **Playwright MCP** | CNKI/万方中文文献检索 | 见 playwright-browser-automation.md |
| **Tavily API**（可选） | 网络上下文搜索备选 | API key 配置 |

### 验证嵌入文件

```
ls skills-embedded/        # 应包含 7 个 .md 文件
ls static/core/            # 应包含 22 个 .md 文件
ls strategists/            # 应包含 6 个 .md 文件
```

## 文件结构

```
academic-coursework/
├── SKILL.md                          # 入口：全自动/半自动模式选择
├── manifest.yaml                     # 声明式加载配置
├── GLOSSARY.md                       # 术语参考（不加载到上下文）
├── auto_mode/                        # 全自动模式
│   ├── orchestrator.md               # 自动编排逻辑
│   └── auto_checks.py                # 自动质量检查
├── static/core/                      # 始终加载（22 文件）
│   ├── gate-chain.md                 # QC1-QC5 门控链
│   ├── pipeline-rules.md             # 核心规则
│   ├── dispatch-points.md            # 调度点表
│   ├── context-budget.md             # Context Window Budget
│   ├── parallel-groups.md            # 并行组
│   ├── result-collection.md          # Result Collection Protocol
│   ├── multi-agent-patterns.md       # 多智能体编排模式
│   ├── stop-and-ask.md               # Stop and Ask Protocol
│   ├── fallback.md                   # "I Don't Know" Fallback
│   ├── input-validation.md           # Input Validation Protocol
│   ├── exit-protocol.md              # Structured Exit Protocol
│   ├── web-search-policy.md          # Web Search Policy
│   ├── paper-types.md                # 论文类型路由表
│   ├── prerequisites.md              # Prerequisites
│   ├── do-dont.md                    # DO/DON'T 规则
│   ├── incremental-update.md         # 增量更新 DAG + 重跑协议
│   ├── stage-output-format.md        # Stage 输出格式规范
│   ├── session-persistence.md        # 断点续传协议
│   ├── session-variables.md          # 外部 API Key 注册与验证
│   ├── attention-defense.md          # 注意力防御
│   ├── convergence-loop.md           # 收敛循环协议
│   └── material-passport.md          # Material Passport
├── strategists/                      # 按需加载（6 文件）
│   ├── C1.md                         # Topic & Arguments
│   ├── C2.md                         # Literature Search
│   ├── C3.md                         # Write Draft (.docx)
│   ├── C4.md                         # 6-Dimension Review
│   ├── C5.md                         # Revision & Convergence
│   └── C5.5.md                       # 提交前注水（隐藏分支）
├── references/                       # 条件/按需加载
│   ├── chinese-de-ai-guide.md        # 中文 De-AI 检测指南
│   ├── chinese-de-ai-quick-ref.md    # 中文 De-AI 快速参考
│   ├── playwright-browser-automation.md # 浏览器自动化
│   ├── tavily-search.md              # Tavily API 搜索参考
│   ├── common-mistakes.md            # 常见错误/反模式
│   ├── literature-verify.md          # 文献常态化验证
│   ├── paraphrasing-patterns.md      # 注水用改写模式
├── scripts/                          # Python 脚本
│   ├── __init__.py
│   ├── inflate_paper.py              # 注水脚本
│   ├── merge_vocab.py                # 词汇合并
│   ├── vocab_diversity.py            # 词汇多样性
│   ├── vocab_diversity_data.py       # 词汇多样性数据
│   └── format_adapters/              # 格式适配器
└── skills-embedded/                  # 嵌入技能快照（7 文件）
    ├── scientific-brainstorming.md   # 学术头脑风暴
    ├── docx.md                       # python-docx 参考
    ├── paper-lookup.md               # 文献检索
    ├── markdown-mermaid-writing.md   # Mermaid 图表
    ├── generate-image.md             # AI 图片生成
    ├── pdf.md                        # PDF 处理
    └── latex-thesis-zh.md            # 中文 LaTeX 模板参考
```

## 致谢

部分设计参考 Google PaperOrchestra (arXiv:2604.05018, 2026.04) 的多智能体流水线思路。
