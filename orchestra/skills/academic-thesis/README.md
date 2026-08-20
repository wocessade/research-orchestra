# Academic Thesis Pipeline

中文学位论文从选题到盲审/答辩的完整编排 —— Claude Code 全流程编排器。路由器 + manifest + 按需加载的分块架构（上下文缩减 70-80%）。

## 入口

| 入口 | 适用场景 | 起点 |
|------|---------|------|
| **Bachelor (本科)** | 本科学位论文 | T1 → T2 → T3 → T4 → T5 → T6 → T7 |
| **Master (硕士)** | 硕士/博论 | T1 → T2 → T3 → T4 → T5 → T6 → T7 |
| **Master-Inflated (硕士+注水)** | 硕士论文需降AI率 | T1 → T2 → T3 → T4 → T5 → T6 → T6.7 → T6.5 → T7 |
| **With-Data (有数据)** | 已有实验数据 | T1 → T1.5 → T2 → T3 → T4 → T5 → T6 → T7 |
| **Existing-Manuscript** | 已有完整初稿 | QE gate → T4 → T5 → T6 → T7 |

## 快速开始

```
用户: "帮我写一篇关于X的本科/硕士论文"
Claude: [路由器读取 manifest → 加载 static/core/ 规则 → 按需加载 strategists/T1-strategist.md]
  → 选题头脑风暴 → 文献检索 → 方法论 → 写作 → 质量评估 → 修订 → 盲审准备
```

## 做的事情

- **入口路由**: 根据 degree (bachelor/master) + discipline (stem/humanities) 自动分流
- **选题与数据探索**: T1 选题头脑风暴 → T1.5（可选）数据探索与可视化
- **文献与方法论**: T2 文献检索 → T3 方法论设计
- **写作**: T4 论文写作（.docx 生成）
- **质量评估与修订**: T5 维度评估 → T6 修订收敛
- **盲审与注水**: T6.5 盲审准备 → T6.7（隐藏分支）注水/降AI → T7 答辩/提交

## 依赖清单

### 内嵌 Skill 参考（skills-embedded/）

流水线已将所有外部 skill 内容打包为本地快照（`skills-embedded/`），无需额外安装。

### 外部软件

| 软件 | 用途 | 安装 |
|------|------|------|
| **Python 3.8+** | docx 生成、评分脚本、文献验证 | `pip install python-docx requests pyyaml` |
| **Playwright MCP** | CNKI/万方中文文献检索 | 见 playwright-browser-automation.md |
| **Tavily API**（可选） | 网络上下文搜索备选 | API key 配置 |
| **LaTeX distribution**（可选） | LaTeX 编译 | TeXLive / MiKTeX |

### 验证嵌入文件

```
ls skills-embedded/   # 应包含 13 个 .md 文件
ls static/core/       # 应包含 22 个 .md 文件
ls strategists/       # 应包含 10 个 .md 文件
```

## 文件结构

```
academic-thesis/
├── SKILL.md                          # 入口：全自动/半自动/步进模式选择
├── manifest.yaml                     # 声明式加载配置
├── README.md                         # 本文档
├── static/core/                      # 始终加载（22 文件）
├── strategists/                      # 按需加载（10 文件）
├── evaluate/                         # 评估子系统（路由到 academic-shared）
│   ├── stage_agents.md               # 路由层（唯一本地文件）
│   └── agents/humanities/            # 人文社科专属 agent（7 文件）
│   └── agents/stem/                  # 理工科专属 agent（9 文件）
├── references/                       # 条件/按需加载
├── skills-embedded/                  # 嵌入技能快照（13 文件）
└── literature/                       # 路由到 academic-shared
```

## 致谢

部分设计参考 Google PaperOrchestra (arXiv:2604.05018, 2026.04) 的多智能体流水线思路。
