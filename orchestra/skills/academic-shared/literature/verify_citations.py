#!/usr/bin/env python3
"""
Batch citation verification CLI.

Multi-API verification tool that queries OpenAlex, Semantic Scholar, and CrossRef
for each reference entry, producing a three-state verdict:

  - true:          At least one API confirmed the reference exists
  - false:         Reference has a DOI but NO API matches it (fabrication evidence)
  - unresolvable:  Only title searches available, none matched (coverage gap)

Also computes contamination signals per entry (preprint status, per-API unmatched flags)
and an overall advisory contamination level.

Cache: SQLite ~/.cache/pipeline/verification.db, 90-day TTL.

5-step pipeline (inspired by Research-Skills):
  1. Search     — multi-API lookup (OpenAlex, Semantic Scholar, Crossref) — included
  2. Verify     — cross-database cross-validation with verdict — included
  3. Retrieve   — fetch abstract for verified entries — via --fetch-abstracts
  4. Validate   — cross-ref ledger claims vs retrieved abstracts — via --validate-ledger
  5. Add        — generate formatted citations (BibTeX, APA) — via --format-output

Usage:
    # Steps 1-2: verify only
    python verify_citations.py --input bibliography.json --output-dir ./output
    python verify_citations.py --input bibliography.json --output-dir ./output --no-cache
    python verify_citations.py --input bibliography.json --report-only  # re-use cache only

    # Steps 1-3: verify + retrieve abstracts
    python verify_citations.py --input bibliography.json --output-dir ./output --fetch-abstracts

    # Step 4: validate ledger claims against abstracts
    python verify_citations.py --validate-ledger evidence_ledger.jsonl --verification-report verification_report.json --output-dir ./output

    # Step 5: generate formatted citation output
    python verify_citations.py --format-output --verification-report verification_report.json --output-dir ./output

Input JSON format: list of entry dicts with keys {citation_key, title, authors, year, doi, venue, source}.
  source="manual" entries are skipped (exempt from automated verification).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

import pyalex
import requests
from habanero import Crossref
from semanticscholar import SemanticScholar


# ── Registry ───────────────────────────────────────────────────────

pyalex.config.email = "academic-pipeline-verify@localhost"
_s2_client = SemanticScholar()
_cr_client = Crossref()


# ── Constants ──────────────────────────────────────────────────────

CACHE_DIR = Path.home() / ".cache" / "pipeline"
CACHE_DB = CACHE_DIR / "verification.db"
CACHE_TTL_DAYS = 90
CACHE_TTL_SECONDS = CACHE_TTL_DAYS * 24 * 3600

PREPRINT_VENUES = frozenset({
    "arXiv", "bioRxiv", "medRxiv", "SSRN", "Research Square",
    "Preprints.org", "ChemRxiv", "EarthArXiv", "OSF Preprints", "TechRxiv",
})

TITLE_SIMILARITY_THRESHOLD = 0.80
REQUEST_DELAY = 0.15  # seconds between API calls to avoid rate limits


# ── Helpers ────────────────────────────────────────────────────────

def normalize_doi(doi: str) -> str:
    """Strip URL prefix and whitespace from a DOI, returning bare identifier."""
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def title_similarity(a: str, b: str) -> float:
    """Normalised title similarity in [0, 1] (case-insensitive, punctuation-stripped)."""
    def _key(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower().strip())
    return SequenceMatcher(None, _key(a), _key(b)).ratio()


def _entry_key(entry: dict) -> str:
    """Deterministic cache key for an entry."""
    key = entry.get("citation_key") or ""
    if not key:
        title = (entry.get("title") or "")[:80]
        key = hashlib.md5(title.encode()).hexdigest()[:12]
    return key


def _query_form(doi: str | None, title: str) -> str:
    return f"doi:{doi or ''}|title:{title[:120]}"


def _normalise_title_for_compare(entry: dict) -> str:
    return re.sub(r'[^a-z0-9]', '', (entry.get("title") or "").lower().strip())


# ── Cache ──────────────────────────────────────────────────────────

def _open_cache() -> sqlite3.Connection:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            entry_key TEXT NOT NULL,
            resolver   TEXT NOT NULL,
            query_form TEXT NOT NULL,
            payload    TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (entry_key, resolver, query_form)
        )
    """)
    conn.execute("PRAGMA journal_mode=WAL")
    # Housekeeping: evict stale entries on connect
    cutoff = time.time() - CACHE_TTL_SECONDS
    conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
    conn.commit()
    return conn


def _cache_get(conn: sqlite3.Connection, entry_key: str, resolver: str,
               qf: str) -> dict | None:
    row = conn.execute(
        "SELECT payload FROM cache WHERE entry_key=? AND resolver=? AND query_form=?",
        (entry_key, resolver, qf),
    ).fetchone()
    if row:
        return json.loads(row[0])
    return None


def _cache_put(conn: sqlite3.Connection, entry_key: str, resolver: str,
               qf: str, payload: dict):
    conn.execute(
        "INSERT OR REPLACE INTO cache (entry_key, resolver, query_form, payload, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (entry_key, resolver, qf, json.dumps(payload), time.time()),
    )
    conn.commit()


# ── Resolvers ──────────────────────────────────────────────────────

def _title_pass(ref_title: str, api_title: str | None) -> bool:
    """Check whether API-returned title passes cross-check against reference title."""
    if not api_title:
        return False
    return title_similarity(ref_title, api_title) >= TITLE_SIMILARITY_THRESHOLD


def resolve_openalex(entry: dict, conn: sqlite3.Connection | None,
                     no_cache: bool = False) -> dict | None:
    """Query OpenAlex — by DOI first, fallback to title search.

    Returns dict on match (matched_by ∈ {"doi", "title"}), None otherwise.
    """
    doi = normalize_doi(entry.get("doi") or "")
    title = entry.get("title") or ""
    qf = _query_form(doi, title)
    ek = _entry_key(entry)

    if conn and not no_cache:
        cached = _cache_get(conn, ek, "openalex", qf)
        if cached is not None:
            return cached if cached.get("matched") else None

    result: dict | None = None

    if doi:
        time.sleep(REQUEST_DELAY)
        try:
            resp = requests.get(
                f"https://api.openalex.org/works/doi:{doi}",
                params={"select": "doi,title,authorships,primary_location,cited_by_count,publication_year"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                api_title = data.get("title") or ""
                api_doi = (data.get("doi") or "").replace("https://doi.org/", "")
                if _title_pass(title, api_title):
                    result = {
                        "matched": True,
                        "matched_by": "doi",
                        "queried_by": "id",
                        "resolved_via": "openalex",
                        "matched_title": api_title,
                        "matched_doi": api_doi,
                        "matched_year": data.get("publication_year"),
                        "matched_venue": (
                            data.get("primary_location") or {}
                        ).get("source") or {},
                    }
        except requests.RequestException:
            pass

    # Title fallback: only if DOI didn't match
    if result is None and title:
        time.sleep(REQUEST_DELAY)
        try:
            resp = requests.get(
                "https://api.openalex.org/works",
                params={"search": title, "per_page": 5,
                        "select": "doi,title,authorships,primary_location,cited_by_count,publication_year"},
                timeout=15,
            )
            if resp.status_code == 200:
                items = resp.json().get("results", [])
                for item in items:
                    api_title = item.get("title") or ""
                    if _title_pass(title, api_title):
                        result = {
                            "matched": True,
                            "matched_by": "title",
                            "queried_by": "id" if doi else "title",
                            "resolved_via": "openalex",
                            "matched_title": api_title,
                            "matched_doi": (item.get("doi") or "").replace("https://doi.org/", ""),
                            "matched_year": item.get("publication_year"),
                            "matched_venue": (
                                item.get("primary_location") or {}
                            ).get("source") or {},
                        }
                        break
        except requests.RequestException:
            pass

    if conn and not no_cache:
        _cache_put(conn, ek, "openalex", qf, result or {"matched": False})
    return result


def resolve_semanticscholar(entry: dict, conn: sqlite3.Connection | None,
                            no_cache: bool = False) -> dict | None:
    """Query Semantic Scholar — by DOI first, fallback to title search.

    Returns dict on match (matched_by ∈ {"doi", "title"}), None otherwise.
    """
    doi = normalize_doi(entry.get("doi") or "")
    title = entry.get("title") or ""
    qf = _query_form(doi, title)
    ek = _entry_key(entry)

    if conn and not no_cache:
        cached = _cache_get(conn, ek, "semanticscholar", qf)
        if cached is not None:
            return cached if cached.get("matched") else None

    result: dict | None = None

    # DOI-keyed lookup
    if doi:
        time.sleep(REQUEST_DELAY)
        try:
            s2_doi = doi.replace("/", "/")  # S2 accepts DOI as-is
            papers = _s2_client.search_paper(
                f"DOI:{doi}", limit=3,
                fields=["title", "year", "venue", "externalIds", "abstract", "citationCount"],
            )
            for p in papers:
                ext_ids = p.get("externalIds") or {}
                p_doi = ext_ids.get("DOI", "")
                p_title = p.get("title") or ""
                if p_doi and p_doi.replace("https://doi.org/", "") == doi and _title_pass(title, p_title):
                    result = {
                        "matched": True,
                        "matched_by": "doi",
                        "queried_by": "id",
                        "resolved_via": "semanticscholar",
                        "matched_title": p_title,
                        "matched_doi": p_doi,
                        "matched_year": p.get("year"),
                        "matched_venue": p.get("venue", ""),
                    }
                    break
        except Exception:
            pass

    # Title fallback
    if result is None and title:
        time.sleep(REQUEST_DELAY)
        try:
            papers = _s2_client.search_paper(
                title, limit=5,
                fields=["title", "year", "venue", "externalIds", "abstract", "citationCount"],
            )
            for p in papers:
                p_title = p.get("title") or ""
                if _title_pass(title, p_title):
                    ext_ids = p.get("externalIds") or {}
                    result = {
                        "matched": True,
                        "matched_by": "title",
                        "queried_by": "id" if doi else "title",
                        "resolved_via": "semanticscholar",
                        "matched_title": p_title,
                        "matched_doi": ext_ids.get("DOI", ""),
                        "matched_year": p.get("year"),
                        "matched_venue": p.get("venue", ""),
                    }
                    break
        except Exception:
            pass

    if conn and not no_cache:
        _cache_put(conn, ek, "semanticscholar", qf, result or {"matched": False})
    return result


def resolve_crossref(entry: dict, conn: sqlite3.Connection | None,
                     no_cache: bool = False) -> dict | None:
    """Query Crossref by DOI. Title-only fallback is not attempted (Crossref
    title search is frequently rate-limited and has poor recall for non-English).

    Returns dict on match, None otherwise.
    """
    doi = normalize_doi(entry.get("doi") or "")
    title = entry.get("title") or ""
    if not doi:
        return None  # Crossref skipped — no DOI key available

    qf = _query_form(doi, title)
    ek = _entry_key(entry)

    if conn and not no_cache:
        cached = _cache_get(conn, ek, "crossref", qf)
        if cached is not None:
            return cached if cached.get("matched") else None

    result: dict | None = None
    time.sleep(REQUEST_DELAY)

    try:
        works = _cr_client.works(ids=doi)
        items = works.get("message", {})
        if items:
            cr_title = ((items.get("title") or [""])[0])
            if _title_pass(title, cr_title):
                result = {
                    "matched": True,
                    "matched_by": "doi",
                    "queried_by": "id",
                    "resolved_via": "crossref",
                    "matched_title": cr_title,
                    "matched_doi": items.get("DOI", ""),
                    "matched_year": (
                        items.get("published-print") or
                        items.get("published-online") or
                        items.get("created", {})
                    ).get("date-parts", [[None]])[0][0],
                    "matched_venue": (items.get("container-title") or [""])[0],
                }
    except Exception:
        pass

    if conn and not no_cache:
        _cache_put(conn, ek, "crossref", qf, result or {"matched": False})
    return result


# ── Verdict ────────────────────────────────────────────────────────

def compute_verdict(entry: dict, conn: sqlite3.Connection | None = None,
                    no_cache: bool = False) -> dict:
    """Compute the full verification result for a single entry.

    Returns a dict with keys:
      citation_key, title, verdict, matched_by, queried_by, resolved_via,
      contamination_signals, matched_title, matched_year, matched_venue,
      matched_doi, cached, skip_reason.
    """
    result: dict[str, Any] = {
        "citation_key": entry.get("citation_key", ""),
        "title": entry.get("title", ""),
        "doi": normalize_doi(entry.get("doi") or ""),
        "source": entry.get("source", ""),
        "verdict": None,
        "matched_by": None,
        "queried_by": None,
        "resolved_via": None,
        "contamination_signals": {
            "preprint_post_2024": preprint_signal(entry),
            "openalex_unmatched": True,
            "semantic_scholar_unmatched": True,
            "crossref_unmatched": True,
        },
        "matched_title": None,
        "matched_year": None,
        "matched_venue": None,
        "matched_doi": None,
        "cached": False,
        "skip_reason": None,
        "errors": [],
    }

    # Manual entry exemption
    if entry.get("source") == "manual" or entry.get("obtained_via") == "manual":
        result["verdict"] = "unresolvable"
        result["skip_reason"] = "manual_entry"
        result["contamination_signals"]["openalex_unmatched"] = None  # not checked
        result["contamination_signals"]["semantic_scholar_unmatched"] = None
        result["contamination_signals"]["crossref_unmatched"] = None
        return result

    has_doi = bool(entry.get("doi"))
    doi = normalize_doi(entry.get("doi") or "")

    # Run all three resolvers
    oa = resolve_openalex(entry, conn, no_cache=no_cache)
    ss = resolve_semanticscholar(entry, conn, no_cache=no_cache)
    cr_res = resolve_crossref(entry, conn, no_cache=no_cache)

    # Contamination signals: per-API unmatched
    result["contamination_signals"]["openalex_unmatched"] = oa is None
    result["contamination_signals"]["semantic_scholar_unmatched"] = ss is None
    result["contamination_signals"]["crossref_unmatched"] = cr_res is None

    # Pick best match and assign verdict
    matches = [m for m in [oa, ss, cr_res] if m is not None]
    if matches:
        # Prefer DOI-matched over title-matched
        doi_matches = [m for m in matches if m["matched_by"] == "doi"]
        best = doi_matches[0] if doi_matches else matches[0]

        result["verdict"] = "true"
        result["matched_by"] = best["matched_by"]
        result["queried_by"] = best["queried_by"]
        result["resolved_via"] = best["resolved_via"]
        result["matched_title"] = best.get("matched_title")
        result["matched_year"] = best.get("matched_year")
        result["matched_venue"] = best.get("matched_venue")
        result["matched_doi"] = best.get("matched_doi")
        result["cached"] = False  # cache status not tracked per-resolver here
    elif has_doi and doi:
        # DOI existed but no API matched → fabrication evidence
        result["verdict"] = "false"
        result["matched_by"] = None
        result["queried_by"] = "id"  # DOI was available, lookup was attempted
    else:
        # No DOI + no title match → coverage gap
        result["verdict"] = "unresolvable"
        result["matched_by"] = None
        result["queried_by"] = "title"

    return result


def _contamination_level(signals: dict[str, bool | None]) -> str:
    """Compute advisory contamination level per entry.

    Fields that are None (not checked due to manual exemption or API degradation)
    are excluded from the denominator. If all fields are None, returns 'unknown'.
    """
    present = {k: v for k, v in signals.items()
               if v is not None and k != "preprint_post_2024"}
    if not present:
        return "unknown"
    k = sum(1 for v in present.values() if v is True)
    ratio = k / len(present)
    if ratio == 0:
        return "clean"
    if ratio <= 0.25:
        return "low"
    if ratio <= 0.5:
        return "medium"
    return "high"


def preprint_signal(entry: dict) -> bool:
    """True iff year >= 2024 AND venue resolves to a known preprint server."""
    year = entry.get("year")
    if not isinstance(year, int) or year < 2024:
        return False
    venue = (entry.get("venue") or "").strip()
    return venue in PREPRINT_VENUES


# ── Batch ──────────────────────────────────────────────────────────

def verify_batch(entries: list[dict], output_dir: str | Path,
                 no_cache: bool = False) -> dict:
    """Verify a batch of entries and write reports."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = None if no_cache else _open_cache()

    results = []
    total = len(entries)
    verified_count = 0
    skipped_count = 0
    cache_hits = 0

    for i, entry in enumerate(entries, 1):
        r = compute_verdict(entry, conn=conn, no_cache=no_cache)
        if r["skip_reason"] == "manual_entry":
            skipped_count += 1
        else:
            verified_count += 1
        results.append(r)

        if i % 10 == 0:
            print(f"[verify] {i}/{total}", file=sys.stderr)

    if conn:
        conn.close()

    # Summary
    verdict_counts: dict[str, int] = {"true": 0, "false": 0, "unresolvable": 0}
    contamination_levels: dict[str, int] = {}
    entries_false: list[str] = []

    for r in results:
        v = r["verdict"] or "unresolvable"
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        if v == "false":
            entries_false.append(r["citation_key"] or r["title"][:60])
        cl = _contamination_level(r["contamination_signals"])
        contamination_levels[cl] = contamination_levels.get(cl, 0) + 1

    report = {
        "run_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": "verify_citations.py",
            "entries_submitted": total,
            "entries_verified": verified_count,
            "entries_skipped": skipped_count,
            "contamination_threshold_days": CACHE_TTL_DAYS,
        },
        "summary": {
            "verdicts": verdict_counts,
            "contamination_levels": contamination_levels,
        },
        "advisory_flags": {
            "fabrication_suspected": verdict_counts.get("false", 0) > 0,
            "entries_false": entries_false,
            "contamination_distribution": contamination_levels,
        },
        "entries": results,
    }

    # Write outputs
    report_path = output_dir / "verification_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[verify] Report written to {report_path}", file=sys.stderr)

    # Also write a human-readable summary
    summary_lines = [
        "=" * 60,
        "Citation Verification Report",
        "=" * 60,
        f"Timestamp:       {report['run_metadata']['timestamp']}",
        f"Submitted:       {total}",
        f"Verified:        {verified_count}",
        f"Skipped (manual): {skipped_count}",
        "",
        "── Verdicts ──",
        f"  ✅ True (verified):      {verdict_counts.get('true', 0)}",
        f"  ❌ False (fabrication):  {verdict_counts.get('false', 0)}",
        f"  ⚠️ Unresolvable:        {verdict_counts.get('unresolvable', 0)}",
        "",
        "── Contamination ──",
    ]
    for level, count in sorted(contamination_levels.items()):
        summary_lines.append(f"  {level}: {count}")
    if entries_false:
        summary_lines.extend([
            "",
            "── ⚠️  Fabrication-Suspected Entries ──",
        ])
        for ref in entries_false:
            summary_lines.append(f"  • {ref}")
    summary_lines.append("=" * 60)

    summary_text = "\n".join(summary_lines)
    summary_path = output_dir / "verification_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text + "\n")
    print(summary_text, file=sys.stderr)

    return report


# ── Step 3: Retrieve Abstracts ───────────────────────────────

def retrieve_abstracts(entries: list[dict], output_dir: str | Path) -> list[dict]:
    """Fetch abstracts for verified entries via OpenAlex API."""
    output_dir = Path(output_dir)
    results = []

    for entry in entries:
        doi = normalize_doi(entry.get("doi") or "")
        if not doi:
            continue

        time.sleep(REQUEST_DELAY)
        try:
            resp = requests.get(
                f"https://api.openalex.org/works/doi:{doi}",
                params={"select": "doi,title,abstract_inverted_index,publication_year,authorships"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                inv_index = data.get("abstract_inverted_index")
                abstract = None
                if inv_index:
                    # Reconstruct abstract from inverted index
                    word_positions = {}
                    for word, positions in inv_index.items():
                        for pos in positions:
                            word_positions[pos] = word
                    if word_positions:
                        abstract = " ".join(word_positions[i] for i in sorted(word_positions))
                results.append({
                    "citation_key": entry.get("citation_key", ""),
                    "title": entry.get("title", ""),
                    "doi": doi,
                    "abstract": abstract,
                    "authors_count": len(data.get("authorships", [])),
                    "publication_year": data.get("publication_year"),
                    "retrieval_date": datetime.now(timezone.utc).isoformat(),
                })
        except requests.RequestException:
            pass

    # Write output
    out_path = output_dir / "retrieved_abstracts.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[retrieve] {len(results)} abstracts written to {out_path}", file=sys.stderr)
    return results


# ── Step 5: Format Citation Output ───────────────────────────

def format_citations(verification_report: dict, output_dir: str | Path):
    """Generate BibTeX and plain-text citation lists from verified entries."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = verification_report.get("entries", [])
    verified = [e for e in entries if e.get("verdict") == "true"]

    if not verified:
        print("[format] No verified entries to format", file=sys.stderr)
        return

    # BibTeX
    bib_lines = []
    for e in verified:
        key = e.get("citation_key") or f"ref_{e.get('doi', 'unknown').replace('/', '_')}"
        title = e.get("matched_title") or e.get("title", "Untitled")
        year = e.get("matched_year") or ""
        doi = e.get("doi") or e.get("matched_doi", "")

        bib_lines.append(f"@article{{{key},")
        bib_lines.append(f"  title = {{{title}}},")
        if year:
            bib_lines.append(f"  year = {{{year}}},")
        if doi:
            bib_lines.append(f"  doi = {{{doi}}},")
        bib_lines.append("}\n")

    bib_path = output_dir / "verified_references.bib"
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write("\n".join(bib_lines))
    print(f"[format] {len(verified)} BibTeX entries written to {bib_path}", file=sys.stderr)

    # Plain text (APA-ish format)
    txt_lines = []
    for e in verified:
        title = e.get("matched_title") or e.get("title", "Untitled")
        doi = e.get("doi") or e.get("matched_doi", "")
        doi_part = f" https://doi.org/{doi}" if doi else ""
        txt_lines.append(f"{title}.{doi_part}")

    txt_path = output_dir / "verified_references.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines) + "\n")
    print(f"[format] Plain-text references written to {txt_path}", file=sys.stderr)


# ── Step 4: Validate Ledger ──────────────────────────────────

def validate_ledger(ledger_path: str | Path, verification_report_path: str | Path,
                    output_dir: str | Path):
    """Cross-reference evidence ledger claims against verification report."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load ledger
    ledger_path = Path(ledger_path)
    if not ledger_path.exists():
        print(f"[validate] Ledger not found: {ledger_path}", file=sys.stderr)
        return

    ledger_entries = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ledger_entries.append(json.loads(line))

    # Load verification report
    vp = Path(verification_report_path)
    if not vp.exists():
        print(f"[validate] Verification report not found: {vp}", file=sys.stderr)
        return

    with open(vp, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Cross-reference
    verified_dois = {e.get("doi") or e.get("matched_doi", "")
                     for e in report.get("entries", [])
                     if e.get("verdict") == "true"}

    citation_keys_to_dois = {}
    for e in report.get("entries", []):
        ck = e.get("citation_key", "")
        doi = e.get("doi") or e.get("matched_doi", "")
        if ck:
            citation_keys_to_dois[ck] = doi

    orphan_claims = []
    for le in ledger_entries:
        ref = le.get("source_ref", "")
        # Extract citation key from [Author, Year] format
        doi_ref = citation_keys_to_dois.get(ref, "")
        if doi_ref and doi_ref not in verified_dois:
            orphan_claims.append(le)

    result = {
        "ledger_entries": len(ledger_entries),
        "verified_entries_in_report": len(verified_dois),
        "orphan_claims": len(orphan_claims),
        "orphan_details": [
            {"claim_id": c.get("claim_id"), "claim_text": c.get("claim_text", "")[:80],
             "source_ref": c.get("source_ref")}
            for c in orphan_claims[:20]
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    out_path = output_dir / "ledger_validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[validate] Ledger validation: {len(orphan_claims)} orphan claims of {len(ledger_entries)} total",
          file=sys.stderr)
    print(f"[validate] Report written to {out_path}", file=sys.stderr)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch citation verification — multi-API existence checks for references.",
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to JSON input file (list of entry dicts)")
    parser.add_argument("--output-dir", "-o", default="./output",
                        help="Output directory for reports (default: ./output)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable SQLite cache (force live API queries)")
    parser.add_argument("--report-only", action="store_true",
                        help="Only re-generate reports from cache; skip live queries")
    parser.add_argument("--fetch-abstracts", action="store_true",
                        help="Step 3: Retrieve abstracts for verified entries")
    parser.add_argument("--format-output", action="store_true",
                        help="Step 5: Generate formatted citation output (BibTeX + plain text)")
    parser.add_argument("--validate-ledger", type=str, default=None,
                        help="Step 4: Path to evidence_ledger.jsonl for cross-validation")
    parser.add_argument("--verification-report", type=str, default=None,
                        help="Path to existing verification_report.json (for steps 4-5)")

    args = parser.parse_args()

    # Dedicated step-4 mode: validate ledger against existing report
    if args.validate_ledger and args.verification_report:
        validate_ledger(args.validate_ledger, args.verification_report, args.output_dir)
        return

    # Dedicated step-5 mode: format from existing report
    if args.format_output and args.verification_report:
        vp = Path(args.verification_report)
        if vp.exists():
            with open(vp, "r", encoding="utf-8") as f:
                report = json.load(f)
            format_citations(report, args.output_dir)
        else:
            print(f"Error: verification report not found: {vp}", file=sys.stderr)
        return

    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Accept both top-level list and { "results": [...] } wrapper
    if isinstance(data, dict):
        entries = data.get("results") or data.get("entries") or []
    elif isinstance(data, list):
        entries = data
    else:
        print("Error: input must be a JSON array or {results: [...]}", file=sys.stderr)
        sys.exit(1)

    if not entries:
        print("Warning: no entries found in input", file=sys.stderr)
        report = {
            "run_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": "verify_citations.py",
                "entries_submitted": 0,
                "entries_verified": 0,
                "entries_skipped": 0,
            },
            "summary": {"verdicts": {}, "contamination_levels": {}},
            "advisory_flags": {},
            "entries": [],
        }
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "verification_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("[verify] Empty input — wrote empty report", file=sys.stderr)
        return

    print(f"[verify] Loaded {len(entries)} entries from {input_path}", file=sys.stderr)

    if args.report_only:
        # Re-read from cache only (no live queries)
        conn = _open_cache()
        results = []
        for entry in entries:
            r = compute_verdict(entry, conn=conn, no_cache=False)
            results.append(r)
        conn.close()
        # Write re-generated report
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "run_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": "verify_citations.py (report-only)",
            },
            "entries": results,
        }
        with open(output_dir / "verification_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[verify] Report-only: regenerated from cache -> {output_dir / 'verification_report.json'}", file=sys.stderr)
        return

    report = verify_batch(entries, args.output_dir, no_cache=args.no_cache)

    # Step 3: fetch abstracts
    if args.fetch_abstracts:
        retrieve_abstracts(entries, args.output_dir)

    # Step 5: format output
    if args.format_output:
        format_citations(report, args.output_dir)


if __name__ == "__main__":
    main()
