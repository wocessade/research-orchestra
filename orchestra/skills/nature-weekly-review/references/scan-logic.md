# Scan Logic — 扫描、解析、聚合

## Step 1: 确定日期范围

默认 = **本周 ISO 周**（周一至周日）。

```python
from datetime import date, timedelta

def get_iso_week_range(offset_weeks=0):
    today = date.today()
    # shift by offset
    target = today + timedelta(weeks=offset_weeks)
    iso = target.isocalendar()
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    return {
        "year": iso.year, "week": iso.week,
        "monday": monday.isoformat(), "sunday": sunday.isoformat()
    }
```

用户可通过自然语言指定范围：
- "上周" → `offset_weeks=-1`
- "06/23-06/29" → 直接解析 `start/end`
- "第26周" → 查 ISO 周历

## Step 2: 扫描文献笔记

```python
import glob
import yaml
import re
from pathlib import Path

VAULT_DAILY = Path("D:/MD ideas/20-机器学习/文献/每日推送")

def scan_papers(date_range):
    papers = []
    seen_arxiv = set()

    for d in date_range:  # list of "YYYY-MM-DD" strings
        pattern = VAULT_DAILY / d / "*.md"
        for fpath in glob.glob(str(pattern)):
            paper = parse_paper_note(fpath)
            if paper is None:
                continue
            # Dedup by arxiv_id
            aid = paper.get("arxiv", "")
            if aid and aid in seen_arxiv:
                # Keep higher score
                existing = next(p for p in papers if p["arxiv"] == aid)
                if paper["score"] > existing["score"]:
                    papers.remove(existing)
                    papers.append(paper)
                continue
            if aid:
                seen_arxiv.add(aid)
            papers.append(paper)

    papers.sort(key=lambda p: p["score"], reverse=True)
    return papers
```

## Step 3: YAML Frontmatter 解析

```python
def parse_paper_note(fpath):
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return None

    fm = yaml.safe_load(match.group(1))
    body = match.group(2)

    # Parse body sections
    sections = {}
    current_section = None
    for line in body.split("\n"):
        h2 = re.match(r'^## (.+)', line)
        if h2:
            current_section = h2.group(1).strip()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    paper = {
        "title": fm.get("title", ""),
        "authors": fm.get("authors", ""),
        "year": fm.get("year", 0),
        "venue": fm.get("venue", ""),
        "arxiv": fm.get("arxiv", ""),
        "doi": fm.get("doi", ""),
        "score": fm.get("score", 0),
        "classification": fm.get("classification", ""),
        "zotero_key": fm.get("zotero_key", ""),
        "tags": fm.get("tags", []),
        "date_read": fm.get("date_read", ""),
        "sections": {k: "\n".join(v).strip() for k, v in sections.items()},
        "filename": Path(fpath).stem,
        "obsidian_path": str(Path(fpath).relative_to(VAULT_DAILY.parent.parent)),
    }
    return paper
```

## Step 4: 聚合统计

```python
def aggregate_stats(papers):
    if not papers:
        return {"total": 0, "avg_score": 0, "median_score": 0, "A_count": 0}

    scores = [p["score"] for p in papers]
    sorted_scores = sorted(scores)
    n = len(scores)
    median = sorted_scores[n // 2] if n % 2 else (sorted_scores[n//2 - 1] + sorted_scores[n//2]) / 2

    # Score distribution buckets
    buckets = {"0-5": 0, "5-6": 0, "6-7": 0, "7-8": 0, "8-10": 0}
    for s in scores:
        if s < 5: buckets["0-5"] += 1
        elif s < 6: buckets["5-6"] += 1
        elif s < 7: buckets["6-7"] += 1
        elif s < 8: buckets["7-8"] += 1
        else: buckets["8-10"] += 1

    # Classification distribution
    class_dist = {"A_核心主线": 0, "B_章节支撑": 0, "C_工程背景": 0, "D_方法借鉴": 0, "E_暂存低优先": 0}
    for p in papers:
        c = p.get("classification", "")
        if c in class_dist:
            class_dist[c] += 1

    # Tag frequency (Top 15)
    tag_freq = {}
    for p in papers:
        for t in p.get("tags", []):
            tag_freq[t] = tag_freq.get(t, 0) + 1
    top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "total": n,
        "avg_score": round(sum(scores) / n, 1),
        "median_score": median,
        "A_count": class_dist["A_核心主线"],
        "score_distribution": buckets,
        "classification_distribution": class_dist,
        "tag_frequency": top_tags,
    }
```

## 去重规则

- **主键** = `arxiv_id`（arXiv ID 是全局唯一的）
- 同一 arxiv_id 出现在多个日期目录 → 保留 score 最高的那份
- 无 arxiv_id 的论文（稀有情况）→ 按 title 规范化（去标点、小写）去重
- DOI 去重作为次级手段，但 pipeline 输出的大部分论文来自 arXiv 且可能无 DOI
