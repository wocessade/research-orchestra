# academic-journal/evaluate/stage_agents.md

## Purpose

This file routes the S7 `Polish & Review` stage to the correct journal evaluation config and agent set.
It extends the existing English-only journal review path with Chinese domestic journal and Chinese conference review.

The evaluation engine remains `academic-shared/evaluate/scripts/scoring.py`; this file only declares routing behavior.
No new Python script is required.

---

## Required manifest fields used by this router

```yaml
stage: S7
language: en | zh
venue: international | chinese-domestic | chinese-conference
paperType: empirical | literature-review | theory | registered-report | data-paper | software-tool | benchmark
mode: stepping | standard | revision-only | submission-only
```

Optional Chinese journal fields, when available:

```yaml
journalTier: A | B1 | B2 | B3 | C1 | C2 | C3 | D
journalName: "目标期刊名称"
discipline: humanities | social-science | stem | interdisciplinary | unspecified
```

Optional English journal fields, when available:

```yaml
journalTier: T1 | T2 | T3 | T4 | T5
journalName: "Target journal name"
discipline: humanities | social-science | stem | interdisciplinary | unspecified
```

If `journalTier` is missing, the router uses the default tier below.

---

## Route table

| Condition | Resolved tier | Config | Agent source |
|---|---:|---|---|
| `S7 + language=en + venue=international` | T1-T5 (from english_tier_normalization, default T3) | `academic-shared/evaluate/config/english_international.yaml` | `academic-journal/evaluate/agents/english/`, fallback `academic-shared/evaluate/agents/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=A` | A | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=B1` | B1 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=B2` | B2 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=B3` | B3 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=C1` | C1 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=C2` | C2 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-domestic + journalTier=C3` | C3 | `academic-journal/evaluate/config/chinese_core.yaml` | `academic-journal/evaluate/agents/chinese/` |
| `S7 + language=zh + venue=chinese-conference` | D | `academic-journal/evaluate/config/chinese_conference.yaml` | `academic-journal/evaluate/agents/chinese/` |

Default tier rules:

```yaml
defaults:
  english-international: T3   # assume standard international journal when target tier is unknown
  chinese-domestic: B1        # assume CSSCI/北大核心 pressure when target tier is unknown
  chinese-conference: D
```

---

## Chinese tier normalization

Use the following mapping before loading the config:

```yaml
tier_normalization:
  "A": A
  "顶刊": A
  "权威期刊": A
  "中国社会科学": A
  "经济研究": A

  "B1": B1
  "CSSCI核心": B1
  "CSSCI 核心": B1
  "南大核心": B1
  "北大核心+CSSCI": B1

  "B2": B2
  "CSSCI扩展": B2
  "CSSCI 扩展版": B2

  "B3": B3
  "CSCD核心": B3
  "CSCD 核心": B3

  "C1": C1
  "北大核心": C1
  "中文核心": C1

  "C2": C2
  "普刊": C2
  "普通期刊": C2

  "C3": C3
  "入库": C3
  "增刊": C3
  "专刊": C3

  "D": D
  "会议": D
  "中文会议": D

english_tier_normalization:
  "T1": T1
  "Nature": T1
  "Science": T1
  "Cell": T1
  "top-tier": T1
  "top-tier journal": T1
  "field-top": T1

  "T2": T2
  "society journal": T2
  "strong field": T2
  "top subfield": T2

  "T3": T3
  "standard international": T3
  "regular journal": T3

  "T4": T4
  "OA mega": T4
  "open access mega": T4
  "PLOS ONE": T4
  "Scientific Reports": T4
  "mega-journal": T4

  "T5": T5
  "conference": T5
  "international conference": T5
```

---

## Router logic

```pseudo
if manifest.stage != "S7":
    return NO_EVALUATION_ROUTE

if manifest.language == "en":
    route.tier = normalize_english(manifest.journalTier) or "T3"
    route.config = "academic-shared/evaluate/config/english_international.yaml"
    route.agent_dirs = [
        "academic-journal/evaluate/agents/english/",
        "academic-shared/evaluate/agents/"
    ]
    route.context = {
        "journalTier": route.tier,
        "paperType": manifest.paperType,
        "mode": manifest.mode,
        "journalName": manifest.journalName or "unspecified",
        "discipline": manifest.discipline or "unspecified"
    }
    return route

if manifest.language == "zh" and manifest.venue == "chinese-domestic":
    route.tier = normalize(manifest.journalTier) or "B1"
    route.config = "academic-journal/evaluate/config/chinese_core.yaml"
    route.agent_dirs = ["academic-journal/evaluate/agents/chinese/"]
    route.context = {
        "journalTier": route.tier,
        "paperType": manifest.paperType,
        "mode": manifest.mode,
        "journalName": manifest.journalName or "未指定",
        "discipline": manifest.discipline or "unspecified"
    }
    return route

if manifest.language == "zh" and manifest.venue == "chinese-conference":
    route.tier = "D"
    route.config = "academic-journal/evaluate/config/chinese_conference.yaml"
    route.agent_dirs = ["academic-journal/evaluate/agents/chinese/"]
    route.context = {
        "journalTier": "D",
        "paperType": manifest.paperType,
        "mode": manifest.mode,
        "conferenceName": manifest.journalName or "未指定",
        "discipline": manifest.discipline or "unspecified"
    }
    return route

return UNSUPPORTED_ROUTE_WITH_MESSAGE(
    "academic-journal/evaluate supports S7 review for language=en international, language=zh chinese-domestic, and language=zh chinese-conference."
)
```

---

## Agent placement decision

Chinese journal agents must live in:

```text
academic-journal/evaluate/agents/chinese/
```

Do not load thesis Chinese agents directly from `academic-thesis/evaluate/agents/`.
The journal agents may borrow the thesis agents' anti-flattery protocol and triplicate scoring structure, but they are forked and journal-specific because Chinese journal review has different targets: GB/T 7714 references, CSSCI/北大核心/CSCD tier awareness, journal contribution claims, first-round reviewer culture, and paper-type adaptation.
