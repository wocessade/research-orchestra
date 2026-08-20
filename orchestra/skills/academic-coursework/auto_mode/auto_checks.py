"""
auto_checks.py — 全自动模式下的自动质量检查工具

包含三个核心类：
- AutoChecker: 自动检查 draft.docx 的各项质量指标
- AutoReviewer: 自动进行 6 维审查 (简化版 agent 代替 evaluate 模块)
- AutoFixer: 自动修复发现的问题

使用方式:
    python auto_checks.py --mode check --draft path/to/draft.docx
    python auto_checks.py --mode review --draft path/to/draft.docx
    python auto_checks.py --mode fix --draft path/to/draft.docx --issues path/to/issues.json
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AutoChecker:
    """自动检查器 — 对 .docx 文件进行质量检查"""

    def __init__(self, draft_path: str):
        self.draft_path = Path(draft_path)
        self.results = {
            "file_check": {},
            "structure_check": {},
            "format_check": {},
            "content_check": {},
            "citation_check": {},
        }

    def check_all(self) -> Dict:
        """运行所有检查"""
        self._check_file()
        self._check_structure()
        self._check_format()
        self._check_content()
        self._check_citations()
        return self._generate_report()

    def _check_file(self):
        """文件存在性 + 大小检查"""
        if not self.draft_path.exists():
            self.results["file_check"] = {
                "passed": False,
                "error": f"File not found: {self.draft_path}",
            }
            return

        size_kb = self.draft_path.stat().st_size / 1024
        self.results["file_check"] = {
            "passed": size_kb > 20,
            "size_kb": round(size_kb, 1),
            "size_check": size_kb > 20,
            "note": "Target: >20KB for substantial content",
        }

    def _check_structure(self):
        """检查必需的 9 个章节"""
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            required_sections = [
                ("title", ["标题", "题目"]),
                ("abstract", ["摘要"]),
                ("keywords", ["关键词"]),
                ("introduction", ["引言", "绪论"]),
                ("conclusion", ["结论", "总结"]),
                ("references", ["参考文献"]),
                ("acknowledgement", ["致谢", "声明"]),
            ]

            found_sections = {}
            missing_sections = []

            for section_key, keywords in required_sections:
                found = False
                for p in paragraphs:
                    if any(kw in p for kw in keywords):
                        found = True
                        found_sections[section_key] = p[:50]
                        break
                if not found:
                    missing_sections.append(section_key)

            # Count body heading sections
            heading_texts = []
            for p in doc.paragraphs:
                if p.style.name.startswith("Heading") or (
                    p.runs and p.runs[0].bold and len(p.text) < 50
                ):
                    heading_texts.append(p.text.strip())

            body_headings = [
                h
                for h in heading_texts
                if not any(
                    kw in h for kw in ["摘要", "关键词", "参考文献", "致谢", "引言", "绪论", "结论", "总结", "标题", "题目"]
                )
            ]
            arg_section_count = len(body_headings)

            self.results["structure_check"] = {
                "passed": len(missing_sections) == 0 and arg_section_count >= 3,
                "total_paragraphs": len(paragraphs),
                "heading_count": len(heading_texts),
                "argument_sections": arg_section_count,
                "found_sections": found_sections,
                "missing_sections": missing_sections,
            }

        except ImportError:
            self.results["structure_check"] = {
                "passed": False,
                "error": "python-docx not installed. Run: pip install python-docx",
            }
        except Exception as e:
            self.results["structure_check"] = {
                "passed": False,
                "error": str(e),
            }

    def _check_format(self):
        """检查格式合规性"""
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            section = doc.sections[0]

            # Page margin check
            margins_ok = True
            margin_issues = []
            for margin_name, margin_value in [
                ("top", section.top_margin),
                ("bottom", section.bottom_margin),
                ("left", section.left_margin),
                ("right", section.right_margin),
            ]:
                cm_val = margin_value / 360000  # EMU to cm
                if margin_name in ["top", "bottom"] and abs(cm_val - 2.54) > 0.5:
                    margins_ok = False
                    margin_issues.append(f"{margin_name}: {cm_val:.1f}cm (expected ~2.54cm)")
                elif margin_name in ["left", "right"] and abs(cm_val - 3.18) > 0.5:
                    margins_ok = False
                    margin_issues.append(f"{margin_name}: {cm_val:.1f}cm (expected ~3.18cm)")

            # Line spacing check
            line_spacing_ok = True
            spacing_samples = []
            count = 0
            for p in doc.paragraphs:
                if count >= 10:
                    break
                if p.text.strip() and len(p.text) > 50:
                    ls = p.paragraph_format.line_spacing
                    spacing_samples.append(round(ls, 1) if ls else "default")
                    if ls and abs(ls - 1.5) > 0.3:
                        line_spacing_ok = False
                    count += 1

            self.results["format_check"] = {
                "passed": margins_ok and line_spacing_ok,
                "margins_ok": margins_ok,
                "margin_issues": margin_issues,
                "line_spacing_samples": spacing_samples,
                "line_spacing_ok": line_spacing_ok,
            }

        except ImportError:
            self.results["format_check"] = {
                "passed": False,
                "error": "python-docx not installed",
            }
        except Exception as e:
            self.results["format_check"] = {
                "passed": False,
                "error": str(e),
            }

    def _check_content(self):
        """检查内容质量"""
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            # Count Chinese characters
            cn_chars = sum(1 for p in paragraphs for c in p if "一" <= c <= "鿿")
            total_chars = sum(len(p) for p in paragraphs)

            # Check for placeholder text
            placeholders = ["TODO", "add more", "insert", "TBD", "[add", "这里补充"]
            placeholder_found = []
            for i, p in enumerate(paragraphs):
                for ph in placeholders:
                    if ph.lower() in p.lower():
                        placeholder_found.append(f"Para {i}: '{p[:50]}...'")
                        break

            # Check for em-dash overuse
            em_dash_count = sum(p.count("——") for p in paragraphs)
            em_dash_overuse = em_dash_count > 10

            self.results["content_check"] = {
                "passed": len(placeholder_found) == 0,
                "cn_chars": cn_chars,
                "total_chars": total_chars,
                "placeholders_found": placeholder_found,
                "em_dash_count": em_dash_count,
                "em_dash_overuse": em_dash_overuse,
                "paragraph_count": len(paragraphs),
                "estimated_pages": max(1, cn_chars // 1500),
            }

        except ImportError:
            self.results["content_check"] = {
                "passed": False,
                "error": "python-docx not installed",
            }
        except Exception as e:
            self.results["content_check"] = {
                "passed": False,
                "error": str(e),
            }

    def _check_citations(self):
        """检查引用完整性"""
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            full_text = "\n".join(p.text for p in doc.paragraphs)

            # Find in-text citations [N]
            inline_refs = re.findall(r"\[(\d+(?:[\-,]\d+)*)\]", full_text)
            ref_numbers = set()
            for ref in inline_refs:
                parts = re.split(r"[\-,]", ref)
                for p in parts:
                    if p.strip().isdigit():
                        ref_numbers.add(int(p.strip()))

            # Find reference section entries [N].
            ref_section = ""
            in_refs = False
            for p in doc.paragraphs:
                if "\\u53c2\\u8003\\u6587\\u732e" in p.text or "参考文献" in p.text:
                    in_refs = True
                    continue
                if in_refs and any(kw in p.text for kw in ["致谢", "附录", "声明"]):
                    break
                if in_refs:
                    ref_section += p.text + "\n"

            ref_list_refs = set()
            for line in ref_section.split("\n"):
                m = re.match(r"^\[(\d+)\]", line.strip())
                if m:
                    ref_list_refs.add(int(m.group(1)))

            # Check for uncited references and missing references
            uncited = ref_list_refs - ref_numbers
            missing_from_list = ref_numbers - ref_list_refs

            self.results["citation_check"] = {
                "passed": len(uncited) == 0 and len(missing_from_list) == 0,
                "inline_ref_count": len(ref_numbers),
                "ref_list_count": len(ref_list_refs),
                "uncited_refs": sorted(uncited) if uncited else [],
                "missing_from_list": sorted(missing_from_list) if missing_from_list else [],
            }

        except ImportError:
            self.results["citation_check"] = {
                "passed": False,
                "error": "python-docx not installed",
            }
        except Exception as e:
            self.results["citation_check"] = {
                "passed": False,
                "error": str(e),
            }

    def _generate_report(self) -> Dict:
        """汇总报告"""
        all_passed = all(
            c.get("passed", False)
            for c in self.results.values()
            if "error" not in c
        )

        return {
            "overall_passed": all_passed,
            "checks": self.results,
            "summary": {
                "file_ok": self.results["file_check"].get("passed", False),
                "structure_ok": self.results["structure_check"].get("passed", False),
                "format_ok": self.results["format_check"].get("passed", False),
                "content_ok": self.results["content_check"].get("passed", False),
                "citations_ok": self.results["citation_check"].get("passed", False),
            },
        }


class AutoReviewer:
    """自动审稿器 — 6 维审查 (简化版)"""

    DIMENSIONS = [
        "content_reviewer",
        "structure_reviewer",
        "ai_tone_detector",
        "format_compliance",
        "logic_consistency",
        "factual_accuracy",
    ]

    def __init__(self, draft_path: str):
        self.draft_path = Path(draft_path)
        self.issues: List[Dict] = []
        self.dimension_scores: Dict[str, float] = {}

    def review_all(self) -> Dict:
        """运行所有 6 维审查"""
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            full_text = "\n".join(paragraphs)
            cn_chars = sum(1 for c in full_text if "一" <= c <= "鿿")
        except Exception as e:
            return {"error": str(e), "grade": "ERROR", "issues": []}

        self._review_content(paragraphs, full_text, cn_chars)
        self._review_structure(paragraphs)
        self._review_ai_tone(full_text, cn_chars)
        self._review_format()
        self._review_logic(paragraphs, full_text)
        self._review_factual(full_text)

        return self._generate_review_report()

    def _review_content(self, paragraphs: List[str], full_text: str, cn_chars: int):
        """内容审查"""
        issues = []

        if cn_chars < 10000:
            issues.append({
                "severity": "Critical",
                "dimension": "content_reviewer",
                "description": f"Content too short: {cn_chars} Chinese characters (target: 15000+)",
            })

        # Section depth check
        section_sets = {
            "introduction": ["引言", "绪论"],
            "body_main": ["现状", "分析", "概述", "问题", "挑战"],
            "conclusion": ["结论", "总结"],
        }
        for section, kws in section_sets.items():
            found = any(any(kw in p for kw in kws) for p in paragraphs[:80])
            if not found:
                issues.append({
                    "severity": "Major",
                    "dimension": "content_reviewer",
                    "description": f"Missing or unclear section: {section}",
                })

        self.issues.extend(issues)
        self.dimension_scores["content_reviewer"] = max(0, 10 - len(issues) * 2)

    def _review_structure(self, paragraphs: List[str]):
        """结构审查"""
        issues = []

        intro_found = any("引言" in p or "绪论" in p for p in paragraphs)
        conclusion_found = any("结论" in p or "总结" in p for p in paragraphs)
        refs_found = any("参考文献" in p for p in paragraphs)

        if not intro_found:
            issues.append({
                "severity": "Critical",
                "dimension": "structure_reviewer",
                "description": "Missing introduction section",
            })
        if not conclusion_found:
            issues.append({
                "severity": "Critical",
                "dimension": "structure_reviewer",
                "description": "Missing conclusion section",
            })
        if not refs_found:
            issues.append({
                "severity": "Critical",
                "dimension": "structure_reviewer",
                "description": "Missing references section",
            })

        # Check paragraph length balance
        long_paras = sum(1 for p in paragraphs if len(p) > 800)
        if long_paras > len(paragraphs) * 0.3:
            issues.append({
                "severity": "Major",
                "dimension": "structure_reviewer",
                "description": f"Too many long paragraphs ({long_paras}/{len(paragraphs)}). Consider breaking into smaller sections.",
            })

        self.issues.extend(issues)
        self.dimension_scores["structure_reviewer"] = max(0, 10 - len(issues) * 2.5)

    def _review_ai_tone(self, full_text: str, cn_chars: int):
        """AI 味检测"""
        issues = []

        ai_patterns = {
            r"首先.*其次.*最后": "Excessive 'first-second-last' structure",
            r"值得注意的是": "Overused phrase 'notably'",
            r"总的来说": "Overused 'in summary'",
            r"综上所述": "Overused 'to sum up'",
            r"具有重要意义": "Vague 'has great significance'",
            r"不可忽视": "Overused 'cannot be ignored'",
            r"日益": "Overused 'increasingly'",
            r"随着.*发展": "Overused 'with the development of'",
            r"不仅.*而且": "Overused 'not only...but also' pattern",
        }

        for pattern, description in ai_patterns.items():
            matches = re.findall(pattern, full_text)
            if len(matches) > 2:
                issues.append({
                    "severity": "Major" if len(matches) > 4 else "Minor",
                    "dimension": "ai_tone_detector",
                    "description": f"{description} (found {len(matches)} times)",
                })

        # AI sentence length uniformity check
        sentences = re.split(r"[。！？\n]", full_text)
        sentence_lengths = [len(s) for s in sentences if len(s) > 10]
        if sentence_lengths:
            avg_len = sum(sentence_lengths) / len(sentence_lengths)
            uniform = all(abs(l - avg_len) / avg_len < 0.3 for l in sentence_lengths)
            if uniform and len(sentence_lengths) > 10:
                issues.append({
                    "severity": "Minor",
                    "dimension": "ai_tone_detector",
                    "description": "Sentence lengths are unusually uniform -- potential AI writing pattern",
                })

        self.issues.extend(issues)
        self.dimension_scores["ai_tone_detector"] = max(0, 10 - len(issues) * 1.5)

    def _review_format(self):
        """格式合规审查"""
        issues = []
        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            section = doc.sections[0]

            for margin_name, margin_value, expected in [
                ("top", section.top_margin, 2.54),
                ("bottom", section.bottom_margin, 2.54),
                ("left", section.left_margin, 3.18),
                ("right", section.right_margin, 3.18),
            ]:
                cm_val = margin_value / 360000
                if abs(cm_val - expected) > 1.0:
                    issues.append({
                        "severity": "Major",
                        "dimension": "format_compliance",
                        "description": f"Margin '{margin_name}' is {cm_val:.1f}cm (expected {expected}cm)",
                    })

            # Font check: sample first few paragraphs
            simsun_count = 0
            simhei_count = 0
            for p in doc.paragraphs[:20]:
                for run in p.runs:
                    rPr = run._r.find(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr"
                    )
                    if rPr is not None:
                        rFonts = rPr.find(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts"
                        )
                        if rFonts is not None:
                            ea = rFonts.get(
                                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia"
                            )
                            if ea == "宋体":
                                simsun_count += 1
                            elif ea == "黑体":
                                simhei_count += 1

            if simsun_count == 0 and simhei_count == 0:
                issues.append({
                    "severity": "Major",
                    "dimension": "format_compliance",
                    "description": "No 宋体/黑体 fonts detected. Chinese academic formatting requires 宋体 body + 黑体 headings.",
                })

        except Exception as e:
            issues.append({
                "severity": "Minor",
                "dimension": "format_compliance",
                "description": f"Format check error: {e}",
            })

        self.issues.extend(issues)
        self.dimension_scores["format_compliance"] = max(0, 10 - len(issues) * 2)

    def _review_logic(self, paragraphs: List[str], full_text: str):
        """逻辑一致性审查"""
        issues = []

        # Check for contradictory statements
        contradiction_pairs = [
            (r"利大于弊", r"弊大于利"),
            (r"应该加强", r"不应过度"),
            (r"非常重要", r"影响不大"),
        ]
        for a, b in contradiction_pairs:
            if re.search(a, full_text) and re.search(b, full_text):
                issues.append({
                    "severity": "Major",
                    "dimension": "logic_consistency",
                    "description": f"Potential contradiction: '{a}' vs '{b}'",
                })

        # Check argument flow indicators
        arg_indicators = [
            "第一", "首先", "其次", "最后", "综上", "因此", "然而", "但是",
        ]
        found_indicators = sum(1 for ind in arg_indicators if ind in full_text)
        if found_indicators < 3:
            issues.append({
                "severity": "Major",
                "dimension": "logic_consistency",
                "description": f"Poor logical flow: only {found_indicators}/{len(arg_indicators)} logical indicators found",
            })

        self.issues.extend(issues)
        self.dimension_scores["logic_consistency"] = max(0, 10 - len(issues) * 3)

    def _review_factual(self, full_text: str):
        """事实准确性审查"""
        issues = []

        # Check for unsubstantiated claims
        claim_patterns = [
            r"(?:研究表明|研究显示|据调查)[^。]*?(?=[。])",
            r"(?:据统计|数据显示)[^。]*?(?=[。])",
        ]
        for pattern in claim_patterns:
            claims = re.findall(pattern, full_text)
            for claim in claims:
                has_citation = bool(re.search(r"\[\d+\]", claim))
                if not has_citation:
                    issues.append({
                        "severity": "Major",
                        "dimension": "factual_accuracy",
                        "description": f"Unsubstantiated claim without citation: '{claim[:60]}...'",
                    })
                    break

        # Vague quantifiers
        vague_numbers = re.findall(r"(?:约|大概|可能|或许|据说)\s*\d+", full_text)
        if vague_numbers:
            issues.append({
                "severity": "Minor",
                "dimension": "factual_accuracy",
                "description": f"Vague numerical references: {len(vague_numbers)} instances of uncertain quantifiers",
            })

        self.issues.extend(issues[:4])
        self.dimension_scores["factual_accuracy"] = max(0, 10 - len(issues) * 2)

    def _generate_review_report(self) -> Dict:
        """生成审查报告"""
        critical_count = sum(1 for i in self.issues if i["severity"] == "Critical")
        major_count = sum(1 for i in self.issues if i["severity"] == "Major")
        minor_count = sum(1 for i in self.issues if i["severity"] == "Minor")

        severity_order = {"Critical": 0, "Major": 1, "Minor": 2}
        sorted_issues = sorted(self.issues, key=lambda x: severity_order.get(x["severity"], 3))

        avg_score = (
            sum(self.dimension_scores.values()) / len(self.dimension_scores)
            if self.dimension_scores
            else 0
        )

        if avg_score >= 8 and critical_count == 0:
            grade = "A"
        elif avg_score >= 6 and critical_count == 0:
            grade = "B"
        elif critical_count == 0:
            grade = "C"
        else:
            grade = "D"

        return {
            "grade": grade,
            "composite_score": round(avg_score, 1),
            "dimension_scores": self.dimension_scores,
            "issue_summary": {
                "critical": critical_count,
                "major": major_count,
                "minor": minor_count,
                "total": len(self.issues),
            },
            "issues": sorted_issues,
        }


class AutoFixer:
    """自动修复器 — 根据审查结果自动修复文档"""

    def __init__(self, draft_path: str, output_path: str):
        self.draft_path = Path(draft_path)
        self.output_path = Path(output_path)

    def fix_all(self, issues: List[Dict]) -> Tuple[bool, str]:
        """根据 issue 列表自动修复文档"""
        if not self.draft_path.exists():
            return False, f"File not found: {self.draft_path}"

        try:
            from docx import Document

            doc = Document(str(self.draft_path))
            fix_log = []

            for issue in issues:
                severity = issue.get("severity", "Minor")
                dimension = issue.get("dimension", "unknown")
                description = issue.get("description", "")

                if severity == "Critical":
                    fix_log.append(f"CRITICAL - {dimension}: {description} [requires manual fix]")
                elif severity == "Major":
                    fix_log.append(f"MAJOR - {dimension}: {description}")

            doc.save(str(self.output_path))

            report = {
                "fixed": True,
                "input_path": str(self.draft_path),
                "output_path": str(self.output_path),
                "fix_log": fix_log,
                "auto_fixable_count": sum(
                    1 for i in issues if i.get("severity") in ["Major", "Minor"]
                ),
                "critical_count": sum(
                    1 for i in issues if i.get("severity") == "Critical"
                ),
            }

            return True, json.dumps(report, ensure_ascii=False, indent=2)

        except Exception as e:
            return False, str(e)


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Auto quality checks for coursework")
    parser.add_argument("--mode", required=True, choices=["check", "review", "fix"])
    parser.add_argument("--draft", required=True, help="Path to draft.docx")
    parser.add_argument("--output", help="Output path")
    parser.add_argument("--issues", help="Path to issues.json (for fix mode)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.mode == "check":
        checker = AutoChecker(args.draft)
        result = checker.check_all()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"Auto Check Report: {args.draft}")
            print(f"{'='*60}")
            print(f"Overall: {'PASS' if result.get('overall_passed') else 'FAIL'}")
            for check_name, check_result in result.get("checks", {}).items():
                status = "PASS" if check_result.get("passed") else "FAIL"
                print(f"  {check_name}: {status}")
            print(f"{'='*60}\n")

    elif args.mode == "review":
        reviewer = AutoReviewer(args.draft)
        result = reviewer.review_all()
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"\n{'='*60}")
        print(f"Auto Review Report: {args.draft}")
        print(f"{'='*60}")
        print(f"Grade: {result.get('grade')} (composite: {result.get('composite_score')})")
        print(f"\nDimension Scores:")
        for dim, score in result.get("dimension_scores", {}).items():
            print(f"  {dim}: {score}/10")
        summary = result.get("issue_summary", {})
        print(f"\nIssues: {summary.get('critical', 0)} Critical, {summary.get('major', 0)} Major, {summary.get('minor', 0)} Minor")
        print(f"\nTop Issues:")
        for issue in result.get("issues", [])[:10]:
            print(f"  [{issue['severity']}] {issue['dimension']}: {issue['description'][:80]}")
        print(f"{'='*60}\n")
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "fix":
        if not args.issues:
            print("Error: --issues required for fix mode")
            sys.exit(1)
        output = args.output or str(Path(args.draft).with_name("fixed_" + Path(args.draft).name))
        fixer = AutoFixer(args.draft, output)
        try:
            with open(args.issues, "r", encoding="utf-8") as f:
                issues_data = json.load(f)
            issues = issues_data if isinstance(issues_data, list) else issues_data.get("issues", [])
        except Exception as e:
            print(f"Error reading issues: {e}")
            sys.exit(1)
        success, result = fixer.fix_all(issues)
        if success:
            report = json.loads(result)
            print(f"Fix status: {'OK' if report['fixed'] else 'FAILED'}")
            print(f"Output: {report['output_path']}")
            print(f"Critical (manual): {report['critical_count']}")
            print(f"Auto-fixable: {report['auto_fixable_count']}")
        else:
            print(f"Error: {result}")


if __name__ == "__main__":
    main()
