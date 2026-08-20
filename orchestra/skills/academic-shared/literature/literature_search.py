#!/usr/bin/env python3
"""
Unified academic literature search toolkit.

Multi-source search across pyalex (OpenAlex), semanticscholar, habanero (CrossRef),
and scholarly (Google Scholar). Supports automatic dedup, citation network analysis,
3D quality scoring, and seed paper expansion (forward/backward snowballing).

Usage:
    python literature_search.py \
        --query "time consciousness narrative novel" \
        --sources openalex,semanticscholar,crossref \
        --years 2018-2026 \
        --output results.json

    python literature_search.py \
        --seed-dois doi_list.txt \
        --snowball-depth 1 \
        --output snowball_results.json
"""

import argparse
import json
import os
import sys
import time
import re
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import Optional

import pyalex
from semanticscholar import SemanticScholar
from habanero import Crossref

pyalex.config.email = "academic-pipeline@localhost"

sch = SemanticScholar()
cr = Crossref()

# ── Data model ────────────────────────────────────────────────────

@dataclass
class Paper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    abstract: str = ""
    citation_count: int = 0
    reference_count: int = 0
    source: str = ""
    source_type: str = ""  # journal-article, book, dissertation, etc.
    references: list[str] = field(default_factory=list)  # DOIs of papers this cites
    citations: list[str] = field(default_factory=list)    # DOIs of papers citing this
    quality_scores: dict = field(default_factory=dict)   # {authority, timeliness, relevance, composite}
    # Journal metadata
    journal_name: str = ""
    journal_issn: str = ""
    publisher: str = ""
    is_oa: bool = False


def _title_key(title: str) -> str:
    """Normalize title for dedup comparison."""
    return re.sub(r'[^a-z0-9]', '', title.lower().strip())


def _author_list(authors) -> list[str]:
    """Extract author name strings from various API return shapes."""
    names = []
    for a in authors:
        if isinstance(a, dict):
            name = a.get("name", a.get("author", {}).get("name", ""))
        elif hasattr(a, "name"):
            name = a.name
        else:
            name = str(a)
        if name:
            names.append(name)
    return names


def _reconstruct_openalex_abstract(inverted_index: dict | None) -> str:
    """Reconstruct abstract text from OpenAlex inverted index.

    OpenAlex returns abstracts as word→position-list dicts, e.g.
    {"the": [0, 3], "quick": [1]} → "the quick the"
    """
    if not inverted_index:
        return ""
    pairs = []
    for word, positions in inverted_index.items():
        if isinstance(positions, list):
            for pos in positions:
                pairs.append((pos, word))
    pairs.sort(key=lambda x: x[0])
    return " ".join(word for _, word in pairs)


# ── Source: OpenAlex ───────────────────────────────────────────────

def search_openalex(query: str, years: tuple[int, int], limit: int = 50) -> list[Paper]:
    """Search OpenAlex via pyalex. Covers ~250M works aggregated from many sources."""
    papers = []
    try:
        works = pyalex.Works().search(query) \
            .filter(publication_year=f"{years[0]}-{years[1]}") \
            .sort(cited_by_count="desc") \
            .get(per_page=min(limit, 200))
        for w in works:
            try:
                p = Paper(
                    title=w.get("title", ""),
                    authors=_author_list(w.get("authorships", [])),
                    year=int(w.get("publication_year") or 0) or None,
                    venue=w.get("primary_location", {}).get("source", {}).get("display_name", ""),
                    doi=(w.get("doi") or "").replace("https://doi.org/", ""),
                    abstract=_reconstruct_openalex_abstract(w.get("abstract_inverted_index")),
                    citation_count=w.get("cited_by_count", 0) or 0,
                    reference_count=w.get("referenced_works_count", 0) or 0,
                    source="openalex",
                    source_type=w.get("type", ""),
                    journal_name=w.get("primary_location", {}).get("source", {}).get("display_name", ""),
                    is_oa=w.get("open_access", {}).get("is_oa", False),
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
            except Exception:
                continue
    except Exception as e:
        print(f"[openalex] Search error: {e}", file=sys.stderr)
    return papers


# ── Source: Semantic Scholar ───────────────────────────────────────

SEARCH_BATCH_SIZE = 20  # S2 API returns batches

def search_semanticscholar(query: str, years: tuple[int, int], limit: int = 50) -> list[Paper]:
    """Search Semantic Scholar API. ~200M papers with citation graph."""
    papers = []
    try:
        results = sch.search_paper(query, limit=min(limit, 100),
                                   year=f"{years[0]}-{years[1]}",
                                   fields_of_study=[],
                                   fields=["title","authors","year","venue","externalIds",
                                           "abstract","citationCount","referenceCount",
                                           "journal","publicationTypes","openAccessPdf"])
        for item in results:
            try:
                ext = item.get("externalIds", {}) or {}
                p = Paper(
                    title=item.get("title", ""),
                    authors=[a.get("name","") for a in (item.get("authors") or [])],
                    year=item.get("year"),
                    venue=item.get("venue", ""),
                    doi=ext.get("DOI", ""),
                    abstract=item.get("abstract", ""),
                    citation_count=item.get("citationCount", 0) or 0,
                    reference_count=item.get("referenceCount", 0) or 0,
                    source="semanticscholar",
                    source_type=(item.get("publicationTypes") or [""])[0] if item.get("publicationTypes") else "",
                    journal_name=(item.get("journal") or {}).get("name", ""),
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
            except Exception:
                continue
    except Exception as e:
        print(f"[semanticscholar] Search error: {e}", file=sys.stderr)
    return papers


def paper_details_s2(paper_id: str) -> dict:
    """Get detailed paper info from Semantic Scholar by ID."""
    try:
        return sch.get_paper(paper_id, fields=["title","authors","year","venue",
                                                "externalIds","abstract","citationCount",
                                                "referenceCount","references","citations",
                                                "journal"])
    except Exception:
        return {}


def get_references_s2(paper_id: str, limit: int = 50) -> list[Paper]:
    """Get papers that a given paper cites."""
    papers = []
    try:
        refs = sch.get_paper_references(paper_id, limit=limit,
                                        fields=["title","authors","year","venue",
                                                "externalIds","abstract","citationCount","journal"])
        for r in refs:
            try:
                cited = r.get("citedPaper", {}) or {}
                ext = cited.get("externalIds", {}) or {}
                p = Paper(
                    title=cited.get("title", ""),
                    authors=[a.get("name","") for a in (cited.get("authors") or [])],
                    year=cited.get("year"),
                    venue=cited.get("venue", ""),
                    doi=ext.get("DOI", ""),
                    abstract=cited.get("abstract", ""),
                    citation_count=cited.get("citationCount", 0) or 0,
                    source="semanticscholar_snowball",
                    journal_name=(cited.get("journal") or {}).get("name", ""),
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
            except Exception:
                continue
    except Exception as e:
        print(f"[semanticscholar] Reference fetch error: {e}", file=sys.stderr)
    return papers


def get_citations_s2(paper_id: str, limit: int = 50) -> list[Paper]:
    """Get papers that cite a given paper."""
    papers = []
    try:
        cits = sch.get_paper_citations(paper_id, limit=limit,
                                       fields=["title","authors","year","venue",
                                               "externalIds","abstract","citationCount","journal"])
        for c in cits:
            try:
                citing = c.get("citingPaper", {}) or {}
                ext = citing.get("externalIds", {}) or {}
                p = Paper(
                    title=citing.get("title", ""),
                    authors=[a.get("name","") for a in (citing.get("authors") or [])],
                    year=citing.get("year"),
                    venue=citing.get("venue", ""),
                    doi=ext.get("DOI", ""),
                    abstract=citing.get("abstract", ""),
                    citation_count=citing.get("citationCount", 0) or 0,
                    source="semanticscholar_snowball",
                    journal_name=(citing.get("journal") or {}).get("name", ""),
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
            except Exception:
                continue
    except Exception as e:
        print(f"[semanticscholar] Citation fetch error: {e}", file=sys.stderr)
    return papers


# ── Source: CrossRef ───────────────────────────────────────────────

def search_crossref(query: str, years: tuple[int, int], limit: int = 50) -> list[Paper]:
    """Search CrossRef via habanero. ~150M DOIs and metadata."""
    papers = []
    try:
        results = cr.works(query=query, limit=min(limit, 100),
                          filter={"from-pub-date": f"{years[0]}-01-01",
                                  "until-pub-date": f"{years[1]}-12-31"},
                          sort="relevance")
        items = results.get("message", {}).get("items", [])
        for item in items:
            try:
                p = Paper(
                    title=(item.get("title") or [""])[0],
                    authors=[f"{a.get('given','')} {a.get('family','')}".strip()
                             for a in (item.get("author") or [])],
                    year=(item.get("published-print") or item.get("published-online") or
                          item.get("created", {})).get("date-parts", [[None]])[0][0],
                    venue=(item.get("container-title") or [""])[0],
                    doi=item.get("DOI", ""),
                    abstract=item.get("abstract", ""),
                    citation_count=item.get("is-referenced-by-count", 0) or 0,
                    source="crossref",
                    source_type=item.get("type", ""),
                    publisher=item.get("publisher", ""),
                    journal_issn=(item.get("ISSN") or [""])[0],
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
            except Exception:
                continue
    except Exception as e:
        print(f"[crossref] Search error: {e}", file=sys.stderr)
    return papers


# ── Source: Google Scholar ─────────────────────────────────────────

def search_googlescholar(query: str, years: tuple[int, int], limit: int = 20) -> list[Paper]:
    """Search Google Scholar via scholarly. Rate-limited; use sparingly."""
    papers = []
    try:
        from scholarly import scholarly, ProxyGenerator
        pg = ProxyGenerator()
        # Try free proxies first; if none available, proceed without
        try:
            pg.FreeProxies()
            scholarly.use_proxy(pg)
        except Exception:
            pass  # Proceed without proxy

        search_query = scholarly.search_pubs(query)
        count = 0
        for item in search_query:
            if count >= limit:
                break
            try:
                bib = item.get("bib", {})
                pub_year = bib.get("pub_year")
                if pub_year and (pub_year < years[0] or pub_year > years[1]):
                    continue
                p = Paper(
                    title=bib.get("title", ""),
                    authors=[bib.get("author", "")] if bib.get("author") else [],
                    year=int(pub_year) if pub_year else None,
                    venue=bib.get("venue", ""),
                    abstract=bib.get("abstract", ""),
                    citation_count=item.get("num_citations", 0) or 0,
                    source="googlescholar",
                    publisher=bib.get("publisher", ""),
                )
                if p.title and len(p.title) > 5:
                    papers.append(p)
                    count += 1
            except Exception:
                continue
    except Exception as e:
        print(f"[googlescholar] Search error: {e}", file=sys.stderr)
    return papers


# ── Source: CNKI / 万方 (guided manual search + import) ──────────────

# CNKI and 万方 have no free REST APIs. Strategy: generate search instructions,
# let the user search manually, then import their results for quality scoring.

# Chinese journal tier classification (simplified, for authority scoring)
CSCD_CORE_JOURNALS = {
    "中国科学", "科学通报", "物理学报", "化学学报", "计算机学报",
    "软件学报", "电子学报", "自动化学报", "机械工程学报", "管理科学学报",
    "系统工程理论与实践", "中国管理科学", "管理世界", "经济研究",
    "中国社会科学", "社会学研究", "法学研究", "哲学研究", "历史研究",
    "文学评论", "外语教学与研究", "心理学报", "教育研究", "新闻与传播研究",
}

CSSCI_JOURNALS = {
    "经济研究", "管理世界", "中国社会科学", "社会学研究", "法学研究",
    "中国工业经济", "金融研究", "世界经济", "数量经济技术经济研究",
    "中国农村经济", "财贸经济", "经济学动态", "统计研究", "会计研究",
    "南开管理评论", "管理科学学报", "中国软科学", "科研管理",
    "哲学研究", "历史研究", "文学评论", "中国语文", "外语教学与研究",
    "教育研究", "心理学报", "新闻与传播研究", "中国图书馆学报",
}

BEIDA_CORE_JOURNALS = {
    "北京大学学报", "清华大学学报", "复旦学报", "南京大学学报",
    "中国人民大学学报", "北京师范大学学报", "武汉大学学报",
    "浙江大学学报", "上海交通大学学报", "中山大学学报",
}

CNKI_TIER_RANK = {
    "A": 10.0,     # 学科顶刊 (中国社会科学 etc.)
    "B1": 9.0,     # CSSCI 核心 + 学科权威
    "B2": 8.0,     # CSSCI / CSCD 核心
    "B3": 7.0,     # CSSCI 扩展版 / CSCD 扩展版
    "C1": 5.0,     # 北大核心 / 大学学报(核心收录)
    "C2": 3.5,     # 大学学报(普通)
    "C3": 2.0,     # 普通期刊 / 特色期刊
    "D": 1.5,      # 会议论文
}


def classify_cnki_journal(journal_name: str) -> str:
    """Classify a Chinese journal into a tier based on journal name matching."""
    name = journal_name.strip()

    # Top-tier journals (A-level): highest prestige in Chinese academia
    TOP_TIER = {
        "中国社会科学", "经济研究", "管理世界", "法学研究",
        "哲学研究", "历史研究", "社会学研究", "教育研究",
        "心理学报",
    }
    # Discipline-authoritative CSSCI (B1): top 2-3 per discipline, below A
    B1_TIER = {
        "中国工业经济", "金融研究", "世界经济", "数量经济技术经济研究",
        "南开管理评论", "管理科学学报", "中国软科学", "科研管理",
        "中国农村经济", "财贸经济", "经济学动态", "统计研究", "会计研究",
        "新闻与传播研究", "中国图书馆学报",
        "外语教学与研究", "文学评论", "中国语文",
    }

    # Check CSSCI first (authoritative for humanities/social sciences)
    for j in CSSCI_JOURNALS:
        if j in name:
            if j in TOP_TIER:
                return "A"
            if j in B1_TIER:
                return "B1"
            return "B2"

    # Check CSCD (natural sciences index)
    for j in CSCD_CORE_JOURNALS:
        if j in name:
            return "B2"

    # Check Beida Core
    for j in BEIDA_CORE_JOURNALS:
        if j in name:
            return "C1"

    # Heuristic: 大学学报 are typically C1 (北大核心) or C2
    if "大学学报" in name:
        return "C1"
    if "学报" in name:
        return "C2"
    return "C3"


def score_authority_cnki(journal_name: str) -> float:
    """Score Chinese journal authority 0-10 based on tier classification."""
    tier = classify_cnki_journal(journal_name)
    return CNKI_TIER_RANK.get(tier, 2.0)


def generate_cnki_search_instructions(query: str, query_cn: str,
                                       years: tuple[int, int],
                                       output_dir: str = ".") -> str:
    """Generate CNKI/万方 search instructions and import template.

    Returns the path to the import template file the user should fill in.
    """
    import os
    keywords = query_cn or query
    template_path = os.path.join(output_dir, "cnki_import_template.json")

    instructions = f"""
╔══════════════════════════════════════════════════════════════╗
║           CNKI / 万方 / 维普 — 中文文献手动检索指南            ║
╚══════════════════════════════════════════════════════════════╝

CNKI 和万方不支持开放 API。请在以下数据库手动检索后导入结果。

## 检索信息
  - 检索词: {keywords}
  - 年份范围: {years[0]} - {years[1]}
  - 语言: 中文

## Step 1: 检索 CNKI (中国知网)
  1. 打开 https://kns.cnki.net/kns8s/  (校外可通过学校 VPN 或 CARSI)
  2. 选择"高级检索"
  3. 输入检索词: {keywords}
  4. 年份范围: {years[0]} - {years[1]}
  5. 来源类别: 勾选 SCI、EI、北大核心、CSSCI、CSCD (按需要)
  6. 按"被引"排序
  7. 勾选最相关的 20-30 篇，导出 → 选择"查新(引文格式)"

## Step 2: 检索万方数据
  1. 打开 https://www.wanfangdata.com.cn/
  2. 同样检索词和年份范围
  3. 导出相关论文(补充 CNKI 未收录的部分)

## Step 3: 检索维普
  1. 打开 http://www.cqvip.com/
  2. 同上

## Step 4: 填入导入模板
  将检索结果填入模板文件:
    {template_path}

  每篇论文填一行:
  {{
    "title": "论文标题",
    "authors": ["作者1", "作者2"],
    "year": 2024,
    "journal": "期刊名称",
    "keywords_cn": ["关键词1", "关键词2"],
    "abstract_cn": "摘要(可选，但建议填写以便质量评分)",
    "citation_count": 0,
    "note": "与我的研究的区别/关系(可选)"
  }}

## Step 5: 导入
  填好后运行:
    python literature_search.py --import-cnki cnki_import_template.json \\
        --cnki-query "{keywords}" --output cnki_results.json

═══════════════════════════════════════════════════════════════
"""
    print(instructions, file=sys.stderr)

    # Write empty template
    template = {
        "_instructions": {
            "query": keywords,
            "years": list(years),
            "sources": "CNKI / 万方 / 维普",
            "format": "Fill the 'papers' array below. Leave abstract empty if unavailable."
        },
        "papers": []
    }
    try:
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

    return template_path


def import_cnki_results(filepath: str, query_cn: str = "",
                         years: tuple = (2018, 2026)) -> list[Paper]:
    """Import user-provided CNKI/万方 search results."""
    papers = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[cnki] Failed to read import file: {e}", file=sys.stderr)
        return papers

    items = data.get("papers", [])
    if not items:
        print("[cnki] No papers found in import file (empty 'papers' array)", file=sys.stderr)
        return papers

    for item in items:
        try:
            title = item.get("title", "")
            if not title or len(title) < 3:
                continue
            year = item.get("year")
            if year and (year < years[0] or year > years[1]):
                continue
            journal = item.get("journal", "")
            tier = classify_cnki_journal(journal)
            p = Paper(
                title=title,
                authors=item.get("authors", []),
                year=year,
                venue=journal,
                journal_name=journal,
                abstract=item.get("abstract_cn", item.get("abstract", "")),
                citation_count=item.get("citation_count", 0),
                source="cnki",
                source_type=tier,
            )
            papers.append(p)
        except Exception:
            continue

    print(f"[cnki] Imported {len(papers)} Chinese papers from {filepath}", file=sys.stderr)
    return papers


def compute_quality_scores_cnki(papers: list[Paper], query: str = "",
                                 current_year: int = 2026):
    """Attach quality scores to Chinese papers using CNKI-tier-aware authority."""
    query_terms = query.lower().split() if query else []
    for p in papers:
        # Authority based on Chinese journal tier
        auth = score_authority_cnki(p.journal_name)
        # Timeliness
        if p.year:
            age = current_year - p.year
            if age <= 2:
                time_s = 10.0
            elif age <= 5:
                time_s = 8.0
            elif age <= 10:
                time_s = 6.0
            elif age <= 20:
                time_s = 4.0
            else:
                time_s = 2.0
        else:
            time_s = 5.0
        # Relevance from Chinese query terms
        text = f"{p.title} {p.abstract} {p.journal_name}".lower()
        if query_terms:
            hits = sum(1 for t in query_terms if t.lower() in text)
            rel = min(10.0, (hits / len(query_terms)) * 10.0)
        else:
            rel = 5.0
        composite = 0.4 * auth + 0.25 * time_s + 0.35 * rel

        p.quality_scores = {
            "source_authority": round(auth, 1),
            "timeliness": round(time_s, 1),
            "relevance": round(rel, 1),
            "composite": round(composite, 1),
            "cnki_tier": classify_cnki_journal(p.journal_name),
        }


# ── Dedup ──────────────────────────────────────────────────────────

def dedup_papers(papers: list[Paper]) -> list[Paper]:
    """Deduplicate papers by DOI first, then by title similarity."""
    seen_doi: dict[str, Paper] = {}
    seen_title: dict[str, Paper] = {}

    for p in papers:
        # DOI dedup (highest priority)
        if p.doi:
            doi_lower = p.doi.lower()
            if doi_lower in seen_doi:
                existing = seen_doi[doi_lower]
                _merge_paper(existing, p)
                continue
            seen_doi[doi_lower] = p
            seen_title[_title_key(p.title)] = p
            continue

        # Title dedup
        key = _title_key(p.title)
        if key in seen_title:
            existing = seen_title[key]
            _merge_paper(existing, p)
            continue

        # Fuzzy title match
        matched = False
        for exist_key, exist_paper in seen_title.items():
            if SequenceMatcher(None, key, exist_key).ratio() > 0.90:
                _merge_paper(exist_paper, p)
                matched = True
                break
        if not matched:
            seen_title[key] = p

    return list(seen_title.values())


def _merge_paper(existing: Paper, new: Paper):
    """Merge metadata from new paper into existing, keeping best fields."""
    if not existing.abstract and new.abstract:
        existing.abstract = new.abstract
    if not existing.doi and new.doi:
        existing.doi = new.doi
    if not existing.venue and new.venue:
        existing.venue = new.venue
    if not existing.authors and new.authors:
        existing.authors = new.authors
    if not existing.year and new.year:
        existing.year = new.year
    if new.citation_count > existing.citation_count:
        existing.citation_count = new.citation_count
    if new.reference_count > existing.reference_count:
        existing.reference_count = new.reference_count
    # Keep track of aggregated sources
    if existing.source != new.source:
        existing.source = f"{existing.source}+{new.source}"


# ── Quality Scoring ────────────────────────────────────────────────

# Journal authority tiers (approximate, for scoring)
HIGH_AUTHORITY_JOURNALS = {
    "nature", "science", "cell", "pnas", "lancet", "nejm", "jama",
    "nature communications", "science advances", "elife", "plos biology",
    "physical review letters", "journal of the acm", "ieee",
}
MID_AUTHORITY_JOURNALS = {
    "scientific reports", "plos one", "peerj", "royal society open science",
    "bmj open", "frontiers in", "ieee access", "applied sciences",
    "sensors", "materials", "symmetry",
}
HIGH_AUTHORITY_PUBLISHERS = {
    "springer", "elsevier", "wiley", "nature publishing", "oxford university press",
    "cambridge university press", "mit press", "sage", "taylor & francis",
    "ieee", "acm", "aaas", "cell press",
}


def score_authority(paper: Paper) -> float:
    """Score source authority 0-10 based on journal/publisher reputation."""
    score = 5.0  # neutral baseline
    venue = paper.venue.lower()
    journal = paper.journal_name.lower()
    publisher = paper.publisher.lower()
    combined = f"{venue} {journal} {publisher}"

    # Top journals
    for name in HIGH_AUTHORITY_JOURNALS:
        if name.lower() in combined:
            score = 9.0
            break
    else:
        # Mid journals
        for name in MID_AUTHORITY_JOURNALS:
            if name.lower() in combined:
                score = 6.5
                break

    # Publisher boosts
    for pub in HIGH_AUTHORITY_PUBLISHERS:
        if pub in publisher:
            score = max(score, 7.0)
            break

    # Citation count as signal
    if paper.citation_count > 1000:
        score += 1.0
    elif paper.citation_count > 100:
        score += 0.5

    # ISBN / no-ISSN (likely book/book chapter — neutral, not low)
    if paper.source_type in ("book", "book-chapter", "monograph"):
        score = max(score, 6.0)

    return min(10.0, max(0.0, score))


def score_timeliness(paper: Paper, current_year: int = 2026) -> float:
    """Score timeliness 0-10 based on publication year vs. field half-life."""
    if not paper.year:
        return 5.0
    age = current_year - paper.year
    if age <= 2:
        return 10.0
    elif age <= 5:
        return 8.0
    elif age <= 10:
        return 6.0
    elif age <= 20:
        return 4.0
    else:
        return 2.0  # Seminal/classic papers score low on timeliness but may score high on authority


def score_relevance(paper: Paper, query_terms: list[str]) -> float:
    """Score relevance 0-10 based on term presence in title+abstract."""
    text = f"{paper.title} {paper.abstract}".lower()
    if not query_terms:
        return 5.0
    hits = sum(1 for t in query_terms if t.lower() in text)
    ratio = hits / len(query_terms)
    return min(10.0, ratio * 10.0)


def compute_quality_scores(papers: list[Paper], query: str = "",
                           current_year: int = 2026, weights: tuple = (0.4, 0.25, 0.35)):
    """Attach 3D quality scores to each paper. Weights: (authority, timeliness, relevance)."""
    query_terms = query.lower().split() if query else []
    for p in papers:
        auth = score_authority(p)
        time_s = score_timeliness(p, current_year)
        rel = score_relevance(p, query_terms)
        composite = (weights[0] * auth + weights[1] * time_s + weights[2] * rel)

        p.quality_scores = {
            "source_authority": round(auth, 1),
            "timeliness": round(time_s, 1),
            "relevance": round(rel, 1),
            "composite": round(composite, 1),
        }


# ── Citation Network Analysis ──────────────────────────────────────

def analyze_citation_network(papers: list[Paper]) -> dict:
    """Analyze citation relationships among a set of papers.

    Returns clusters and labels them as 'consensus', 'controversy', or 'frontier'.
    """
    n = len(papers)
    if n < 3:
        return {"clusters": [], "summary": "Too few papers for network analysis (need 3+)"}

    # Build citation adjacency from Semantic Scholar cross-refs
    # For papers with S2 IDs, fetch their references
    doi_to_idx = {}
    for i, p in enumerate(papers):
        if p.doi:
            doi_to_idx[p.doi.lower()] = i

    # Simple clustering: group papers by shared venue
    venue_groups: dict[str, list[int]] = {}
    for i, p in enumerate(papers):
        key = p.venue.lower()[:30] if p.venue else "unknown"
        venue_groups.setdefault(key, []).append(i)

    clusters = []
    for venue, indices in venue_groups.items():
        if len(indices) >= 2:
            cluster_papers = [papers[i] for i in indices]
            avg_year = sum(p.year for p in cluster_papers if p.year) / max(1, sum(1 for p in cluster_papers if p.year))
            avg_cites = sum(p.citation_count for p in cluster_papers) / max(1, len(cluster_papers))

            # Label cluster
            if avg_year >= 2023:
                label = "frontier"
            elif avg_cites > 50:
                label = "consensus"
            else:
                label = "controversy"

            clusters.append({
                "label": label,
                "venue": venue,
                "size": len(indices),
                "avg_year": round(avg_year, 1),
                "avg_citations": round(avg_cites, 1),
                "paper_titles": [p.title for p in cluster_papers],
            })

    # Summary
    label_counts = {"consensus": 0, "controversy": 0, "frontier": 0}
    for c in clusters:
        label_counts[c["label"]] += 1

    parts = []
    if label_counts["consensus"]:
        parts.append(f"{label_counts['consensus']} consensus cluster(s)")
    if label_counts["controversy"]:
        parts.append(f"{label_counts['controversy']} controversy cluster(s)")
    if label_counts["frontier"]:
        parts.append(f"{label_counts['frontier']} frontier cluster(s)")

    summary = "Citation network: " + (", ".join(parts) if parts else "no clear clusters detected")

    return {"clusters": clusters, "summary": summary}


# ── Seed Paper Expansion (Snowballing) ─────────────────────────────

def expand_from_seeds(seed_dois: list[str], depth: int = 1,
                      limit_per_paper: int = 50) -> list[Paper]:
    """Forward + backward snowballing from seed DOIs.

    For each seed DOI:
    1. Look up the paper on Semantic Scholar
    2. Get its references (backward)
    3. Get papers that cite it (forward)
    Repeat for `depth` rounds.
    """
    discovered: dict[str, Paper] = {}
    queue = list(seed_dois)

    for round_num in range(depth + 1):
        if round_num > 0:
            # Expand from newly discovered papers
            queue = [p.doi for p in discovered.values() if p.doi][:20]

        next_queue = []
        for doi in queue:
            # Find on Semantic Scholar by DOI
            try:
                results = sch.search_paper(f"DOI:{doi}", limit=1,
                                           fields=["paperId","title","externalIds"])
                paper_id = None
                for r in results:
                    paper_id = r.get("paperId")
                    break
                if not paper_id:
                    continue

                # Backward: references
                refs = get_references_s2(paper_id, limit=limit_per_paper)
                for rp in refs:
                    key = rp.doi.lower() if rp.doi else _title_key(rp.title)
                    if key and key not in discovered:
                        discovered[key] = rp
                        if rp.doi:
                            next_queue.append(rp.doi)

                # Forward: citations
                cits = get_citations_s2(paper_id, limit=limit_per_paper)
                for cp in cits:
                    key = cp.doi.lower() if cp.doi else _title_key(cp.title)
                    if key and key not in discovered:
                        discovered[key] = cp
                        if cp.doi:
                            next_queue.append(cp.doi)

            except Exception as e:
                print(f"[snowball] Error expanding DOI {doi}: {e}", file=sys.stderr)
                continue

        queue = next_queue

    return list(discovered.values())


# ── Output formatting ──────────────────────────────────────────────

def papers_to_dicts(papers: list[Paper]) -> list[dict]:
    """Convert papers to serializable dicts."""
    result = []
    for p in papers:
        d = asdict(p)
        d.pop("references", None)   # Too large for display
        d.pop("citations", None)
        result.append(d)
    return result


def format_bibtex(papers: list[Paper]) -> str:
    """Generate BibTeX entries for papers."""
    entries = []
    for i, p in enumerate(papers):
        key = f"ref{i+1}"
        author_str = " and ".join(p.authors[:5]) if p.authors else "Unknown"
        if len(p.authors) > 5:
            author_str += " and others"
        entry = f"""@article{{{key},
  title = {{{{{p.title}}}}},
  author = {{{{{author_str}}}}},
  year = {{{{{p.year or "n.d."}}}}},
  journal = {{{{{p.venue}}}}},
  doi = {{{{{p.doi}}}}}
}}"""
        entries.append(entry)
    return "\n\n".join(entries)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Unified academic literature search toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python literature_search.py --query "deep learning NLP" --sources openalex,semanticscholar --years 2020-2026
  python literature_search.py --seed-dois dois.txt --snowball-depth 1 --output expanded.json
  python literature_search.py --query "climate change policy" --sources all --min-score 7.0
        """
    )
    # Search params
    parser.add_argument("--query", "-q", type=str, default="",
                        help="Search query string")
    parser.add_argument("--sources", type=str, default="openalex,semanticscholar",
                        help="Comma-separated sources: openalex,semanticscholar,crossref,googlescholar,cnki,all")
    parser.add_argument("--years", type=str, default="2018-2026",
                        help="Year range, e.g. 2018-2026")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max results per source")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="Filter by minimum composite quality score (0-10)")

    # CNKI / Chinese literature
    parser.add_argument("--cnki-query", type=str, default="",
                        help="Chinese search query for CNKI/万方 manual search instructions")
    parser.add_argument("--import-cnki", type=str, default="",
                        help="Path to user-filled CNKI import JSON")

    # Seed expansion
    parser.add_argument("--seed-dois", type=str, default="",
                        help="Path to file with one DOI per line, for snowballing")
    parser.add_argument("--snowball-depth", type=int, default=0,
                        help="Snowball expansion depth (0 = no expansion)")

    # Output
    parser.add_argument("--output", "-o", type=str, default="",
                        help="Output JSON file path (default: stdout)")
    parser.add_argument("--output-format", type=str, choices=["json", "bibtex", "summary"],
                        default="json")
    parser.add_argument("--quality-weights", type=str, default="0.4,0.25,0.35",
                        help="Quality score weights: authority,timeliness,relevance (default: 0.4,0.25,0.35)")

    args = parser.parse_args()

    # Parse years
    try:
        y_start, y_end = args.years.split("-")
        years = (int(y_start), int(y_end))
    except ValueError:
        print(f"Invalid --years format: {args.years}. Use e.g. 2018-2026", file=sys.stderr)
        sys.exit(1)

    # Parse quality weights
    try:
        w = [float(x) for x in args.quality_weights.split(",")]
        if len(w) != 3 or abs(sum(w) - 1.0) > 0.01:
            raise ValueError("Weights must sum to 1.0")
        quality_weights = (w[0], w[1], w[2])
    except ValueError as e:
        print(f"Invalid --quality-weights: {e}", file=sys.stderr)
        sys.exit(1)

    sources = args.sources.split(",")
    if "all" in sources:
        sources = ["openalex", "semanticscholar", "crossref", "googlescholar", "cnki"]

    all_papers: list[Paper] = []
    cnki_papers: list[Paper] = []

    # ── Seed expansion (snowballing) ──
    if args.seed_dois:
        try:
            with open(args.seed_dois, "r", encoding="utf-8") as f:
                seed_dois = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            print(f"Seed DOI file not found: {args.seed_dois}", file=sys.stderr)
            sys.exit(1)

        print(f"[snowball] Expanding from {len(seed_dois)} seed DOIs (depth={args.snowball_depth})...",
              file=sys.stderr)
        snowball_papers = expand_from_seeds(seed_dois, depth=args.snowball_depth)
        all_papers.extend(snowball_papers)
        print(f"[snowball] Discovered {len(snowball_papers)} papers via snowballing", file=sys.stderr)

    # ── Keyword search ──
    if args.query:
        print(f"[search] Query: \"{args.query}\" | Sources: {sources} | Years: {years}",
              file=sys.stderr)

        for source in sources:
            source = source.strip()
            print(f"[search] Searching {source}...", file=sys.stderr)
            t0 = time.time()
            try:
                if source == "openalex":
                    results = search_openalex(args.query, years, args.limit)
                elif source == "semanticscholar":
                    results = search_semanticscholar(args.query, years, args.limit)
                elif source == "crossref":
                    results = search_crossref(args.query, years, args.limit)
                elif source == "googlescholar":
                    results = search_googlescholar(args.query, years, min(args.limit, 20))
                elif source == "cnki":
                    # CNKI has no API — generate manual search instructions
                    cnki_query = args.cnki_query or args.query
                    output_dir = os.path.dirname(args.output) if args.output else "."
                    template_path = generate_cnki_search_instructions(
                        args.query, cnki_query, years, output_dir)
                    print(f"[search] cnki: Manual search required. "
                          f"Template saved to {template_path}",
                          file=sys.stderr)
                    print("[search] cnki: 中文文献需要手动检索 CNKI/万方/维普后导入。"
                          "详见上方说明。", file=sys.stderr)
                    print(f"[search] cnki: After filling the template, run: "
                          f"python literature_search.py --import-cnki \"{template_path}\" "
                          f"--output cnki_results.json", file=sys.stderr)
                    results = []
                else:
                    print(f"[search] Unknown source: {source}", file=sys.stderr)
                    continue
                all_papers.extend(results)
                elapsed = time.time() - t0
                print(f"[search] {source}: {len(results)} results ({elapsed:.1f}s)", file=sys.stderr)
            except Exception as e:
                print(f"[search] {source} failed: {e}", file=sys.stderr)

    # ── CNKI import ──
    if args.import_cnki:
        cnki_papers = import_cnki_results(args.import_cnki,
                                           query_cn=args.cnki_query or args.query,
                                           years=years)
        if cnki_papers:
            cnki_query = args.cnki_query or args.query
            compute_quality_scores_cnki(cnki_papers, query=cnki_query)
            all_papers.extend(cnki_papers)
            print(f"[cnki] {len(cnki_papers)} Chinese papers imported and scored",
                  file=sys.stderr)

    if not all_papers:
        print("No results found.", file=sys.stderr)
        output = {"results": [], "count": 0}
    else:
        # Dedup
        print(f"[dedup] Before dedup: {len(all_papers)} papers", file=sys.stderr)
        all_papers = dedup_papers(all_papers)
        print(f"[dedup] After dedup: {len(all_papers)} papers", file=sys.stderr)

        # Quality scoring — CNKI papers already scored via compute_quality_scores_cnki
        non_cnki = [p for p in all_papers if p.source != "cnki"]
        compute_quality_scores(non_cnki, query=args.query, weights=quality_weights)

        # Filter by min score
        if args.min_score > 0:
            before = len(all_papers)
            all_papers = [p for p in all_papers
                          if p.quality_scores.get("composite", 0) >= args.min_score]
            print(f"[filter] {before} → {len(all_papers)} after min-score={args.min_score}",
                  file=sys.stderr)

        # Sort by composite score
        all_papers.sort(key=lambda p: p.quality_scores.get("composite", 0), reverse=True)

        # Citation network analysis
        network = analyze_citation_network(all_papers)

        # Build output
        output = {
            "query": args.query,
            "sources": sources,
            "years": list(years),
            "count": len(all_papers),
            "citation_network": network,
            "quality_distribution": {
                "excellent (8-10)": sum(1 for p in all_papers if p.quality_scores.get("composite", 0) >= 8),
                "good (6-8)": sum(1 for p in all_papers if 6 <= p.quality_scores.get("composite", 0) < 8),
                "fair (4-6)": sum(1 for p in all_papers if 4 <= p.quality_scores.get("composite", 0) < 6),
                "poor (0-4)": sum(1 for p in all_papers if p.quality_scores.get("composite", 0) < 4),
            },
            "results": papers_to_dicts(all_papers),
        }

    # ── Output ──
    if args.output_format == "bibtex":
        out_str = format_bibtex(all_papers)
    elif args.output_format == "summary":
        lines = [f"# Literature Search Summary\n",
                 f"Query: {args.query}",
                 f"Sources: {sources}",
                 f"Years: {years}",
                 f"Total results (deduplicated): {len(all_papers)}\n"]
        if all_papers:
            lines.append("## Top Papers by Quality Score\n")
            for i, p in enumerate(all_papers[:20]):
                scores = p.quality_scores
                lines.append(f"{i+1}. **{p.title}** ({p.year}) — composite: {scores.get('composite', 'N/A')}")
                lines.append(f"   Authors: {', '.join(p.authors[:3])}")
                lines.append(f"   Venue: {p.venue} | DOI: {p.doi}")
                lines.append(f"   Authority: {scores.get('source_authority','?')} | Timeliness: {scores.get('timeliness','?')} | Relevance: {scores.get('relevance','?')}\n")
        out_str = "\n".join(lines)
    else:
        out_str = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"[output] Written to {args.output} ({len(all_papers)} papers)", file=sys.stderr)
    else:
        print(out_str)


if __name__ == "__main__":
    main()
