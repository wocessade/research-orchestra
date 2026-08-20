# Academic Journal Pipeline

英文学术期刊论文从选题到投稿的完整编排 —— Claude Code 全流程编排器。路由器 + manifest + 按需加载的分块架构（上下文缩减 70-80%）。

## 入口

| 入口 | 适用场景 | 起点 |
|------|---------|------|
| **Idea-First (标准-实证)** | 有想法但无数据 | S0 → S1 → S1.5 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 |
| **Data-First (数据优先)** | 已有数据需要论文 | D0 → D1 → D2 → S0.5 → S1 → S1.5 → S2 → ... |
| **Existing-Manuscript** | 已有完整初稿 | QE gate → S5 → S6 → S7 → S8 → S9 |
| **Preprint (预印本)** | 预印本转投稿 | S8.25 → S6 → S7 → S8 → S9 |
| **Chinese-Domestic** | 中文期刊投稿 | S8.6 → S7 → S8 → S9 |
| **Literature-Review** | 纯文献综述 | S2-LR → S3 → S4 → S5 → ... |

## 快速开始

```
用户: "帮我写一篇关于X的期刊论文"
Claude: [路由器读取 manifest → 加载 static/core/ 规则 → 按需加载 strategists/S0-strategist.md]
  → 选题定义 → 文献检索 → 方法论 → 写作 → 质量评估 → 修订 → 投稿
```

## 做的事情

- **入口路由**: 根据用户状态自动选择 Idea-First、Data-First、Existing-Manuscript 等路径
- **选题与设计**: S0 选题定义 → S1 文献检索 → S1.5 研究设计
- **方法论与写作**: S2 方法论 → S3 结果 → S4 写作
- **质量评估**: S5 自查 → S6 深度碰撞 → S7 六维评估
- **修订与投稿**: S8 修订收敛 → S9 投稿

## 依赖清单

### 内嵌 Skill 参考（skills-embedded/）

流水线已将所有外部 skill 内容打包为本地快照（`skills-embedded/`），无需额外安装。

### 外部软件

| 软件 | 用途 | 安装 |
|------|------|------|
| **Python 3.8+** | 评分脚本、文献验证 | `pip install requests pyyaml` |
| **Playwright MCP** | 浏览器自动化检索 | 见 playwright-browser-automation.md |
| **Tavily API**（可选） | 网络上下文搜索备选 | API key 配置 |
| **Zotero**（可选） | 文献管理 | 见 pyzotero.md |
| **LaTeX distribution**（可选） | LaTeX 编译 | TeXLive / MiKTeX |

### 验证嵌入文件

```
ls skills-embedded/   # 应包含 39 个 .md 文件
ls static/core/       # 应包含 22 个 .md 文件
ls strategists/       # 应包含 24 个 .md 文件
```

## 文件结构

```
academic-journal/
├── SKILL.md                          # 入口：全自动/半自动/步进模式选择
├── manifest.yaml                     # 声明式加载配置
├── README.md                         # 本文档
├── stepping/                         # 步进模式编排
│   ├── orchestrator.md               # 步进编排器
│   ├── quality_monitor.md            # 质量监控
│   └── review_checklist.md           # 作者核对清单
├── static/core/                      # 始终加载（22 文件）
├── strategists/                      # 按需加载（24 文件）
├── evaluate/                         # 评估子系统（路由到 academic-shared）
│   ├── stage_agents.md               # 路由层（唯一本地文件）
│   └── agents/english/               # 英文专属 agent（10 文件）
├── references/                       # 条件/按需加载
├── skills-embedded/                  # 嵌入技能快照（39 文件）
└── literature/                       # 路由到 academic-shared
```

## 致谢

部分设计参考 Google PaperOrchestra (arXiv:2604.05018, 2026.04) 的多智能体流水线思路。
