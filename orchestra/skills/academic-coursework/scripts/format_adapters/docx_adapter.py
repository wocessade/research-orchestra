"""
Analyse a thesis .docx and extract format parameters.

Two strategies (tried in order):
  1. **Named styles** — reads paragraph-style definitions (Normal, Heading 1-3).
  2. **Paragraph sampling** — scans real content and clusters by formatting.

Returns a partial template dict — only keys that could be confidently extracted
are included; everything else falls through to the built-in default.
"""

from collections import Counter
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.shared import Emu


# ── unit conversions ──

def _emu_to_cm(emu: int | None) -> float | None:
    if emu is None:
        return None
    return round(emu / 360000, 2)


def _emu_to_pt(emu: int | None) -> float | None:
    if emu is None:
        return None
    return round(emu / 12700, 1)


# ── XML helpers ──

def _rPr_of_style(style):
    return style.element.find(qn("w:rPr"))


def _pPr_of_style(style):
    return style.element.find(qn("w:pPr"))


def _rPr_of_para(para):
    for run in para._element.findall(qn("w:r")):
        rPr = run.find(qn("w:rPr"))
        if rPr is not None:
            return rPr
    return para._element.find(qn("w:rPr"))


def _pPr_of_para(para):
    return para._element.find(qn("w:pPr"))


def _get_east_asia_font(rPr):
    if rPr is None:
        return None
    rFonts = rPr.find(qn("w:rFonts"))
    return rFonts.get(qn("w:eastAsia")) if rFonts is not None else None


def _get_latin_font(rPr):
    if rPr is None:
        return None
    rFonts = rPr.find(qn("w:rFonts"))
    return (rFonts.get(qn("w:ascii")) or rFonts.get(qn("w:hAnsi"))) if rFonts is not None else None


def _get_size_pt(rPr):
    if rPr is None:
        return None
    sz = rPr.find(qn("w:sz"))
    if sz is not None and sz.get(qn("w:val")):
        return round(int(sz.get(qn("w:val"))) / 2, 1)
    return None


def _get_bold(rPr):
    if rPr is None:
        return None
    b = rPr.find(qn("w:b"))
    if b is None:
        return False
    return b.get(qn("w:val")) not in ("false", "0", None)


def _get_para_align(pPr):
    if pPr is None:
        return None
    jc = pPr.find(qn("w:jc"))
    return jc.get(qn("w:val")) if jc is not None else None


def _get_line_spacing(pPr):
    if pPr is None:
        return None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is not None:
        line = spacing.get(qn("w:line"))
        if line:
            rule = spacing.get(qn("w:lineRule"))
            if rule is None or rule == "auto":
                return round(int(line) / 240, 2)
    return None


def _get_indent(pPr):
    if pPr is None:
        return None
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        return None
    result = {}
    fl = ind.get(qn("w:firstLine"))
    if fl:
        result["first_line_indent"] = f"{_emu_to_cm(int(fl))}cm"
    left = ind.get(qn("w:left"))
    if left:
        result["left_indent"] = f"{_emu_to_cm(int(left))}cm"
    return result or None


def _get_space(pPr):
    if pPr is None:
        return None
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        return None
    result = {}
    before = spacing.get(qn("w:before"))
    if before:
        result["space_before"] = f"{_emu_to_pt(int(before))}pt"
    after = spacing.get(qn("w:after"))
    if after:
        result["space_after"] = f"{_emu_to_pt(int(after))}pt"
    return result or None


def _find_named_style(doc, style_id):
    for s in doc.styles:
        if s.type == 1 and s.style_id == style_id:
            return s
    return None


# ── paragraph sampling ──

def _extract_para_format(para):
    rPr = _rPr_of_para(para)
    pPr = _pPr_of_para(para)
    text = para.text.strip()
    return {
        "font_cn": _get_east_asia_font(rPr),
        "size": _get_size_pt(rPr),
        "bold": _get_bold(rPr),
        "align": _get_para_align(pPr),
        "indent": _get_indent(pPr),
        "space": _get_space(pPr),
        "line_spacing": _get_line_spacing(pPr),
        "text": text[:60],
        "len": len(text),
    }


def _sample_paragraphs(doc, max_para=300):
    samples = []
    for para in doc.paragraphs[:max_para]:
        text = para.text.strip()
        if not text:
            continue
        samples.append(_extract_para_format(para))
    return samples


def _role_from_signature(fmt):
    is_centered = fmt.get("align") == "center"
    is_bold = fmt.get("bold") is True
    size = fmt.get("size") or 0
    if is_centered and is_bold and size >= 14:
        return "chapter_title"
    if is_bold and size >= 12 and not is_centered:
        if size >= 14:
            return "section_h1"
        return "section_h2"
    return None


def _is_default_value(key: str, val) -> bool:
    if isinstance(val, str) and val.startswith("0"):
        return True
    if isinstance(val, (int, float)) and val == 0:
        return True
    return False


def _cluster_by_role(samples):
    clusters: dict[str, list] = {"body": []}
    for fmt in samples:
        role = _role_from_signature(fmt)
        if role is not None:
            clusters.setdefault(role, []).append(fmt)
        else:
            text_len = fmt.get("len", 0)
            if text_len < 30 and fmt.get("align") == "center":
                continue
            clusters["body"].append(fmt)
    return clusters


def _aggregate(cluster):
    if not cluster:
        return None
    keys = ("font_cn", "size", "bold", "align", "line_spacing")
    result = {}
    for key in keys:
        vals = [p[key] for p in cluster if p.get(key) is not None and not _is_default_value(key, p[key])]
        if vals:
            counter = Counter(vals)
            result[key] = counter.most_common(1)[0][0]
    if "size" in result and isinstance(result["size"], (int, float)):
        sz = result["size"]
        result["size"] = f"{int(sz)}pt" if sz == int(sz) else f"{sz}pt"
    if "bold" not in result:
        result["bold"] = False
    if "align" not in result:
        result["align"] = "both"
    sorted_cluster = sorted(cluster, key=lambda p: p.get("len", 0), reverse=True)
    for key in ("indent", "space"):
        for p in sorted_cluster:
            val = p.get(key)
            if val is not None:
                filtered = {k: v for k, v in val.items() if not _is_default_value(k, v)}
                if filtered:
                    result.update(filtered)
                    break
    return result if result else None


_ROLE_STYLE_MAP: dict[str, str] = {
    "body": "Normal",
    "chapter_title": "Heading 1",
    "section_h1": "Heading 2",
    "section_h2": "Heading 3",
}


# ── main ──

def parse(source_path: str) -> dict:
    """Analyse a thesis .docx and return a partial template dict."""
    doc = DocxDocument(source_path)
    result: dict = {}

    # 1. Page setup
    try:
        sec = doc.sections[0]
        result["page"] = {
            "paper": "A4",
            "width_cm": _emu_to_cm(sec.page_width),
            "height_cm": _emu_to_cm(sec.page_height),
            "margins": {
                "top": _emu_to_cm(sec.top_margin),
                "bottom": _emu_to_cm(sec.bottom_margin),
                "left": _emu_to_cm(sec.left_margin),
                "right": _emu_to_cm(sec.right_margin),
            },
            "header_distance": _emu_to_cm(sec.header_distance),
            "footer_distance": _emu_to_cm(sec.footer_distance),
        }
        print("  [OK] Page setup extracted")
    except Exception as e:
        print(f"  [SKIP] Page setup: {e}")

    # 2. Named paragraph styles
    styles_config: dict = {}
    for role, style_id in _ROLE_STYLE_MAP.items():
        s = _find_named_style(doc, style_id)
        if s is None:
            continue
        entry = {}
        rPr = _rPr_of_style(s)
        pPr = _pPr_of_style(s)
        cn = _get_east_asia_font(rPr)
        if cn:
            entry["font_cn"] = cn
        en = _get_latin_font(rPr)
        if en:
            entry["font_en"] = en
        sz = _get_size_pt(rPr)
        if sz:
            entry["size"] = f"{sz}pt"
        b = _get_bold(rPr)
        if b is not None:
            entry["bold"] = b
        align = _get_para_align(pPr)
        if align:
            entry["alignment"] = align
        ls = _get_line_spacing(pPr)
        if ls:
            entry["line_spacing"] = ls
        ind = _get_indent(pPr)
        if ind:
            entry.update(ind)
        sp = _get_space(pPr)
        if sp:
            entry.update(sp)
        if entry:
            entry["status"] = "confirmed"
            styles_config[role] = entry
            print(f"  [OK] Named style '{style_id}' -> {role} ({len(entry)} fields)")

    # 3. Paragraph sampling (fallback for missing styles)
    missing_roles = [r for r in _ROLE_STYLE_MAP if r not in styles_config]
    if missing_roles:
        samples = _sample_paragraphs(doc, max_para=300)
        clusters = _cluster_by_role(samples)
        for role in missing_roles:
            cluster = clusters.get(role)
            if not cluster or len(cluster) < 2:
                continue
            agg = _aggregate(cluster)
            if agg:
                agg["status"] = "confirmed"
                styles_config[role] = agg
                print(f"  [OK] Sampled {role} ({len(cluster)} paragraphs) -> {agg.get('size', '?')}, "
                      f"bold={agg.get('bold')}, align={agg.get('align')}")

    if styles_config:
        result["styles"] = styles_config
    return result
