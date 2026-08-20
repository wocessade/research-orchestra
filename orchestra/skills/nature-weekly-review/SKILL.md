---
name: nature-weekly-review
description: "Generate weekly literature review HTML report from Obsidian daily paper notes. Trigger on 周报, 文献周报, 组会, 每周总结, weekly review."
---

# Nature Weekly Review

从 Obsidian 每日文献笔记生成 HTML 周报，用于组会汇报。

**核心原则：周报是你自己的思考输出，不是自动化流水线的末端。**
Pipeline 负责自动化收集筛选，但周报里的判断、批判、关联必须来自你的理解。
因此本 skill 是 **讨论驱动** 的两阶段流程：先讨论形成观点，再生成报告。

## 两阶段工作流

```
用户触发 ("生成本周文献周报")
  │
  ├── Phase 1: 讨论 (Discussion)
  │   │
  │   ├── 1.1 确定日期范围 (默认当前 ISO 周)
  │   ├── 1.2 扫描 + 聚合 (Glob Notes → YAML parse → stats)
  │   ├── 1.3 呈现结构化摘要
  │   │    · 统计卡片 (总数/均分/中位数/A类)
  │   │    · 每篇论文卡片 (标题/分数/分类/主张/方法/标签)
  │   │    · 标签频率
  │   │    · 与上周对比 (总数/均分变化) — 如果有上周数据
  │   │
  │   ├── 1.4 引导讨论 (逐篇 + 跨篇)
  │   │    对每篇论文 (尤其是 A 类和高分):
  │   │      - 核心主张你怎么看？认同/怀疑/无关？
  │   │      - 方法和你的研究方向有什么关联？
  │   │      - 有什么批判？(可靠/泛化/数据/代码)
  │   │      - 值得精读吗？为什么？
  │   │
  │   │    跨论文:
  │   │      - 这周论文之间有什么联系？有没有值得注意的主题趋势？
  │   │      - 发现了什么 research gap？
  │   │      - 有没有哪篇让你想深入追？
  │   │
  │   └── 1.5 等待用户确认 → "可以出提纲了"
  │
  ├── Phase 2: 提纲确认 (Outline Approval)
  │   │
  │   ├── 2.1 基于讨论内容整理报告提纲
  │   │    逐 section 列出：
  │   │      · 封面: 元数据(周/日期/篇数/均分)
  │   │      · 重点论文: 哪几篇？每篇讲什么要点？
  │   │      · 跨论文主题: 用户识别的联系/趋势
  │   │      · 批判汇总: 按类别列出用户的批判意见
  │   │      · 下周计划: 精读/略读/跳过清单
  │   │
  │   ├── 2.2 提纲格式 (纯文本，不要先做 HTML)
  │   │    ┌──────────────────────────────────────┐
  │   │    │   📋 第{N}周文献周报提纲               │
  │   │    │                                      │
  │   │    │   ① 封面: {N}篇, 均分{X}, A类{M}篇      │
  │   │    │   ② 重点论文 (按重要性排列):            │
  │   │    │      - [Paper X] → 精读, 理由: ...     │
  │   │    │      - [Paper Y] → 略读, 理由: ...     │
  │   │    │   ③ 跨论文主题:                         │
  │   │    │      - 主题A: 论文X + 论文Y → ...       │
  │   │    │   ④ 批判要点:                           │
  │   │    │      - 代码: ...                       │
  │   │    │      - 泛化: ...                       │
  │   │    │   ⑤ 下周计划:                           │
  │   │    │      - 精读: X, Y                      │
  │   │    │      - 速读: Z                         │
  │   │    │      - 跳过: W                         │
  │   │    │   ⑥ 其他: 学习/实践进展 (如有)           │
  │   │    └──────────────────────────────────────┘
  │   │
  │   └── 2.3 用户审核提纲 → 修改/通过 → "生成"
  │       · 用户可以要求增删论文、调整重点、修改判断
  │       · 提纲通过后进入 Phase 3
  │
  └── Phase 3: 生成 (Generation)
      │
      ├── 3.1 将审核通过的提纲内容整理为结构化数据
      │     · 用户确认的每篇论文判断 → A类卡片内容
      │     · 用户确认的跨论文联系 → 跨论文对比
      │     · 用户确认的批判意见 → 批判与空白
      │     · 用户确认的趋势 → 主题聚类
      │
      └── 3.2 生成 HTML
           · 随机选取主题 (6选1)
           · 注入 WEEKLY_DATA JSON
           · 写入: D:/MD ideas/20-机器学习/文献/每周总结/{YYYY-WW}/weekly-report.html
```

## Phase 1: 讨论

### 1.1-1.2 扫描 + 聚合

用 Python 脚本一次性完成扫描和聚合：

```python
from datetime import date, timedelta
import glob, yaml, re, json
from pathlib import Path
from statistics import median

# 确定日期范围 (默认当前 ISO 周)
today = date.today()
monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)
iso = today.isocalendar()

date_list = []
d = monday
while d <= sunday:
    date_list.append(d.isoformat())
    d += timedelta(days=1)

# 扫描
VAULT = Path('D:/MD ideas/20-机器学习/文献/每日推送')
papers = []
seen_arxiv = set()

for ds in date_list:
    for fpath in glob.glob(str(VAULT / ds / '*.md')):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not m: continue
        fm = yaml.safe_load(m.group(1))
        body = m.group(2)
        sections = {}
        cur = None
        for line in body.split('\n'):
            h2 = re.match(r'^## (.+)', line)
            if h2:
                cur = h2.group(1).strip()
                sections[cur] = []
            elif cur:
                sections[cur].append(line)

        paper = {
            'title': fm.get('title',''), 'authors': fm.get('authors',''),
            'year': fm.get('year',0), 'venue': fm.get('venue',''),
            'arxiv': fm.get('arxiv',''), 'score': fm.get('score',0),
            'classification': fm.get('classification',''),
            'tags': fm.get('tags',[]),
            'sections': {k: '\n'.join(v).strip() for k,v in sections.items()},
            'filename': Path(fpath).stem,
            'date_dir': ds,
        }

        aid = paper['arxiv']
        if aid and aid in seen_arxiv:
            existing = next((p for p in papers if p['arxiv']==aid), None)
            if existing and paper['score'] > existing['score']:
                papers.remove(existing); papers.append(paper)
            continue
        if aid: seen_arxiv.add(aid)
        papers.append(paper)

papers.sort(key=lambda p: p['score'], reverse=True)

# 聚合
scores = [p['score'] for p in papers]
n = len(papers)
buckets = {"0-5":0, "5-6":0, "6-7":0, "7-8":0, "8-10":0}
for s in scores:
    if s<5: buckets["0-5"]+=1
    elif s<6: buckets["5-6"]+=1
    elif s<7: buckets["6-7"]+=1
    elif s<8: buckets["7-8"]+=1
    else: buckets["8-10"]+=1

class_dist = {"A_核心主线":0, "B_章节支撑":0, "C_工程背景":0, "D_方法借鉴":0, "E_暂存低优先":0}
for p in papers:
    c = p.get('classification','')
    if c in class_dist: class_dist[c] += 1

tag_freq = {}
for p in papers:
    for t in p.get('tags',[]):
        tag_freq[t] = tag_freq.get(t,0) + 1
top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:15]

stats = {
    "total": n, "avg_score": round(sum(scores)/n,1) if n else 0,
    "median_score": median(scores) if n else 0,
    "A_count": class_dist["A_核心主线"],
    "score_distribution": buckets,
    "classification_distribution": class_dist,
    "tag_frequency": top_tags,
}
```

### 1.3 呈现摘要

将扫描结果以清晰的结构呈现给用户。**不要直接跳到生成 HTML**。格式如下：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2026年 第27周 文献扫描结果
  06/30 — 07/06
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 统计: 5篇 | 均分 7.3 | 中位数 7.5 | A类 1篇
📈 vs 上周: 5→5篇 | 均分 6.8→7.3 ↑

🏷️ 高频标签: 扩散模型 ×2 | 几何估计 ×1 | LLM Unlearning ×1 | ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [按 score 降序排列每篇论文的摘要卡片]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ⭐8.0 [A_核心主线] Alignment Is All You Need For X-to-4D Generation
   🏷️ 4D生成, Alignment, 多模态, 扩散模型, 3D重建
   💡 4D内容生成可解构为3D对齐+时序运动生成
   🔬 Align4D框架，Video-Aligned + Multi-Object Distance Alignment
   ⚠️ 待精读

2. ⭐7.5 [D_方法借鉴] LACUNA: A Testbed for Evaluating Localization...
   ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

同时尝试读取上周数据做对比：

```python
# 读上周周报目录中的 data snapshot (如果有的话)
last_week_dir = f"D:/MD ideas/20-机器学习/文献/每周总结/{year}-W{week-1:02d}/"
# 检查是否存在 data.json (上次生成时保存的)
```

### 1.4 引导讨论

呈现摘要后，**用 AskUserQuestion 引导用户讨论**：

先问总体印象，再逐篇深入。关键是**让用户形成自己的判断**，不要替用户下结论。

**讨论话题模板**（agent 根据实际论文调整，不必逐条问）：

- "这周哪篇最值得关注？"
- "[A类论文标题] — 核心主张你觉得靠谱吗？有什么怀疑的地方？"
- "这几篇之间有联系吗？比如 X 和 Y 是否在用类似的方法解决不同问题？"
- "和你的研究方向有什么关联？需要精读哪篇？"
- "批判角度：方法可靠吗？数据够吗？代码开源了吗？"

Agent 应做：
- 追问模糊的判断 ("你说这个方法有问题，具体是哪里？")
- 帮用户理清论文间的联系 ("你提到了 A 和 B 都用扩散模型，但 A 在像素空间、B 在 latent 空间，这是一个值得对比的点")
- 记录用户的判断，不要覆盖

Agent 禁止做：
- 替用户评价论文优劣
- 在没有用户输入的情况下填写批判内容
- 编造跨论文的深层关联

### 1.5 确认进入提纲阶段

用户明确说"可以出提纲了"、"整理提纲"、"出大纲"等之后，进入 Phase 2。

## Phase 2: 提纲确认

### 重要原则

**不要直接用 HTML 来"预览"提纲。** HTML 生成了就意味着报告定型了，用户看到的是成品而不是提纲，就没有修改的空间了。提纲必须用纯文本呈现，让用户能快速审阅和修改结构。

### 2.1 整理提纲

基于 Phase 1 的讨论内容，整理为结构化的纯文本提纲。

### 2.2 提纲格式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 第27周 (06/30-07/06) 文献周报提纲
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 数据: 5篇 | 均分 7.3 | A类 1篇 | vs上周 +0篇 +0.5分

⭐ 重点论文 (按汇报重要性排列):
  1. [精读] Alignment Is All You Need For X-to-4D — A类
     讲什么: 4D内容生成 = 3D对齐 + 时序运动
     我的判断: 方法solid，Align4D的ODA机制值得关注，和后续可能的方向有关
     讲几分钟: ~3min

  2. [速读] PointDiT — B类
     讲什么: 像素空间DiT做单目几何估计，避免latent失真
     我的判断: 思路好但结果不够惊艳，可以作为方法背景提一下
     讲几分钟: ~1min

  3. [跳过] LACUNA / WorldDirector / Program-as-Weights
     理由: D/E类，暂时和我的方向关联不大

🔬 跨论文主题:
  - 扩散模型方向是本周唯一有重叠的方向 (Miao → 4D生成, Xu → 几何估计)
  - 一个是生成任务，一个是估计任务，方法上有互补性

💬 批判要点:
  - 代码: X 开源, Y 未开源
  - 泛化: [你的判断...]

📝 下周计划:
  - 精读: Miao2026 (用 nature-reader)
  - 速读: Xu2026, Boglioni2026
  - 跳过: Zhang2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  确认后回复"生成"或提出修改意见
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2.3 审核

用户可能：
- 调整论文顺序/"这个应该放前面讲"
- 修改判断/"这个不是泛化问题，是数据问题"
- 增删论文/"这个也值得提一下"
- 调整时间分配/"这个我其实想多讲点"

用户审核通过并回复"生成"、"做吧"、"出报告"等后，进入 Phase 3。

## Phase 3: 生成

### 3.1 整理数据 (不再自动分析)

与旧版不同，Phase 3 不再做 agent 自动分析。所有内容来自用户审核通过的提纲。

| 提纲内容 | 对应 JSON 字段 |
|---------|---------------|
| 用户对每篇论文的判断 | `papers[i].discussion` |
| 用户指定的操作 | `papers[i].action` ("精读"/"速读"/"跳过") |
| 用户发现的跨论文联系 | `cross_paper.user_insights` |
| 用户的批判意见 | `critique_synthesis` |
| 用户发现的趋势 | `theme_clusters` |

### 3.2 生成 HTML

```python
import random, json, os, re
from pathlib import Path

themes = ["academic-clean", "warm-amber", "forest-green",
          "dark-slate", "deep-teal", "midnight-plum"]
theme = random.choice(themes)

template_path = Path.home() / '.claude' / 'skills' / 'nature-weekly-review' / 'templates' / 'weekly-report.html'
with open(template_path, 'r', encoding='utf-8') as f:
    template = f.read()

weekly_data = {
    "meta": {"year": ..., "week": ..., "monday": ..., "sunday": ...},
    "stats": {...},
    "papers": [...],              # 含 discussion 和 action 字段
    "cross_paper": {...},         # 含 user_insights
    "theme_clusters": "...",      # 用户的主题分析
    "critique_synthesis": {...},  # 用户的批判分类
}

html = template.replace(
    'data-theme="academic-clean"',
    f'data-theme="{theme}"'
).replace(
    "WEEKLY_DATA_PLACEHOLDER",
    json.dumps(weekly_data, ensure_ascii=False, indent=2)
)

out_dir = Path(f'D:/MD ideas/20-机器学习/文献/每周总结/{year}-W{week:02d}/')
os.makedirs(out_dir, exist_ok=True)
with open(out_dir / 'weekly-report.html', 'w', encoding='utf-8') as f:
    f.write(html)

# 同时保存 data.json 供下周对比
with open(out_dir / 'data.json', 'w', encoding='utf-8') as f:
    json.dump(weekly_data, f, ensure_ascii=False, indent=2)
```

## WEEKLY_DATA JSON Schema

```json
{
  "meta": {
    "year": 2026, "week": 27,
    "monday": "2026-06-30", "sunday": "2026-07-06"
  },
  "stats": {
    "total": 5, "avg_score": 7.3, "median_score": 7.5, "A_count": 2,
    "score_distribution": {...},
    "classification_distribution": {...},
    "tag_frequency": [...]
  },
  "last_week": {
    "total": 3, "avg_score": 6.8
  },
  "papers": [
    {
      "title": "...", "authors": "...", "year": 2026, "venue": "arXiv",
      "arxiv": "2607.xxxxx", "score": 8.0,
      "classification": "A_核心主线",
      "tags": ["标签1", "标签2"],
      "sections": {
        "核心主张": "...", "方法": "...", "关键发现": "...",
        "批判": "...", "Connection to Research": "...", "下一步": "..."
      },
      "discussion": "用户对这篇论文的判断和评价",
      "action": "精读"
    }
  ],
  "cross_paper": {
    "method_comparison": [...],
    "metrics_comparison": [...],
    "user_insights": "用户发现的跨论文联系"
  },
  "theme_clusters": "用户的主题分析文字",
  "critique_synthesis": {
    "code": [...], "data": [...], "generalization": [...],
    "scale": [...], "theory": [...], "other": [...]
  },
  "generated_at": "2026-07-03T23:00:00"
}
```

## 边界情况

详见 `references/edge-cases.md`：
- 空周: "本周无新文献推送"，跳过讨论直接生成空报告
- 单论文: Phase 1 跳过跨论文讨论题，Phase 3 跨论文对比显示"暂不适用"
- 无 A 类: 讨论时以最高分论文为重点
- 待精读占位符: 呈现时标记 "⚠️ 待精读"，讨论时提醒"这篇还没精读，先看摘要判断"
- 研究方向未定: Connection to Research 保留 "待补充"，不强行填写
- 跨月跨年周: ISO 周计算自然处理

## 验证

生成后用浏览器打开 HTML 检查：
1. 封面数据与扫描结果一致
2. 图表渲染正确
3. 表格可排序（点击表头）
4. Obsidian 链接可点击跳转
5. 侧边栏 IntersectionObserver 高亮
6. 打印预览样式正常

## References

| Reference | 内容 |
|-----------|------|
| `references/scan-logic.md` | 扫描、解析、聚合的 Python 代码 |
| `references/html-template-spec.md` | 8 个 section 的 HTML 结构 |
| `references/chart-spec.md` | Chart.js 图表配置 |
| `references/cross-paper-analysis.md` | 跨论文分析规则（讨论时的参考框架） |
| `references/edge-cases.md` | 边界情况处理 |
| `references/themes.md` | 6 套主题配色 CSS 变量 |
| `templates/weekly-report.html` | 完整 HTML 模板 |
