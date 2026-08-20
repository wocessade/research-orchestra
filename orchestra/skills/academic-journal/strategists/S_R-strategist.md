# Stage S_R: Manuscript Revision [Strategist]

**Trigger:** User submits a manuscript.docx + revision intent (natural language).

**Goal:** Execute a complete revision workflow: segment → capture intent → apply edits → verify.

**Needs Composers:** (none — scripts are self-contained)

**Path conventions:**
- `<shared-scripts>` = `academic-shared/scripts/revision/`（segmenter, assembler）
- `<docx-scripts>` = docx skill 的 `scripts/office/`（unpack.py, pack.py）

---

## Phase A — DOCX Segmentation

**Input:** `manuscript.docx` (path from user)

**Output:** `segments/` directory + `_structure.json` + `_revision_log.md`

### Steps

1. **Unpack the DOCX** using `unpack.py` from docx skill:
   ```
   python <shared-scripts>/unpack.py manuscript.docx unpacked/
   ```
   Save `unpacked/` path for Phase C assembly.

2. **Segment using `docx_segmenter.py`:**
   ```
   python <shared-scripts>/docx_segmenter.py manuscript.docx segments/
   ```

3. **Present summary** to user:
   - Section tree (4 sections, 9 figures, 4 tables — actual numbers)
   - Top-level outline

4. **Load `_structure.json`** for later use (figures list, cross-references).

5. **Write initial `_revision_log.md`** with this format:
   ```markdown
   # Revision Log
   
   Source: manuscript.docx
   Segmented: <timestamp>
   Segments: segments/
   Sections: N
   Figures: N
   Tables: N
   
   ## Operations
   <!-- appended by Phase C -->
   ```

**[Long-task check]** After Phase A, estimate remaining context capacity. If < 30% of original token budget remains → trigger long-task skill to compress prior context before proceeding to Phase B.

---

## Phase B — Intent Capture

**Input:** `segments/_structure.json` (section tree + figures/tables)

**Output:** `_ops.json` (list of operations) + user confirmation

### Steps

1. **Display section tree to user:**
   ```
   SECTIONS:
     front/ (pre-section content — title, abstract, keywords)
     1_引言/
       1.1_研究背景
       1.2_...
     2_材料与方法/
       2.1_...
     ...

   FIGURES: 图1 xxx, 图2 xxx, ... 图9 xxx
   TABLES:  表1 xxx, ... 表4 xxx
   ```

2. **Accept user's revision intent in natural language.** Examples:
   - "全文将'条件A'替换为'SF:药物=1:2'"
   - "在2.9节后新增2.10 CCK细胞毒性实验"
   - "插入图7二级结构图，后序图号顺延"
   - "删除3.5节第二段"

3. **Parse intent into structured operations list.** Operation types:

   | Type | Example | Data |
   |------|---------|------|
   | `global_replace` | A→B in all segments | old_text, new_text |
   | `section_replace` | A→B in specific section | section_path, old_text, new_text |
   | `add_section` | New subsection after 2.9 | after_path, heading, content |
   | `add_paragraph` | New para after P0025 | after_idx, content |
   | `delete_paragraph` | Remove para P0032 | paragraph_idx |
   | `delete_section` | Remove section 3.5 | section_path |
   | `add_figure` | Insert new figure | after_idx, image_path, caption |
   | `renumber_figures` | Renumber all figures sequentially | (none — automatic) |
   | `global_replace_regex` | Regex-based replacement | pattern, replacement |

4. **Show parsed operations to user for confirmation.** Format:
   ```markdown
   ## Proposed Operations
   [1/8] global_replace: "条件A" → "SF:药物=1:2"
   [2/8] global_replace: "条件B" → "SF:药物=1:3"
   ...
   ```

5. **Save to `_ops.json`** in segments/ directory:
   ```json
   [
     {"op": "global_replace", "old": "条件A", "new": "SF:药物=1:2"},
     {"op": "add_section", "after": "2.9", "heading": "2.10 CCK细胞毒性实验", "content": "..."}
   ]
   ```

**[Long-task check]** After Phase B, check context. If phase B consumed significant context in back-and-forth clarification, consider compression before Phase C.

---

## Phase C — Edit Execution

**Input:** `segments/` + `_ops.json` + `unpacked/`

**Output:** `revised.docx` + updated `CHANGES.md` + `.applied_ops`

### Steps

1. **Read `.applied_ops`** (idempotency guard). Skip any operation whose ID is already recorded.

2. **Process each operation** in this order:

   | Order | Op Type | Method |
   |-------|---------|--------|
   | 1 | `global_replace` / `global_replace_regex` | Edit segments/ .md files directly (all) |
   | 2 | `section_replace` | Edit .md files under specific section |
   | 3 | `add_section` | Create section dir + P_new_*.md + heading.md |
   | 4 | `add_paragraph` | Create P_new_NNNN.md in appropriate dir |
   | 5 | `delete_section` | Remove directory and its .md files |
   | 6 | `delete_paragraph` | Remove .md file |
   | 7 | `add_figure` | Update _structure.json + add P_new_*.md for caption |
   | 8 | `renumber_figures` | Call `renumber_figures()` logic (update _structure.json) |
   | 9 | `assemble` | Run docx_assembler.py |

   **Details for each type:**

   - **global_replace**: Iterate all .md files in segments/, perform string replacement. Record as `RO{n}` in `.applied_ops`.
   - **add_section**: Create directory `segments/N.N_subsection/`. Create heading .md file. Create P_new_*.md for body paragraphs.
   - **add_paragraph**: Create P_new_{after_idx}.md in the appropriate section directory.
   - **delete_paragraph**: Remove the .md file from segments/. The assembler won't copy that paragraph.
   - **add_figure**: Update `figures` in `_structure.json`. Add caption paragraph as P_new_*.md. Update `renumber_figures()` in structure. Copy image to appropriate location for manual insertion.
   - **renumber_figures**: Run renumber_figures() on `_structure.json`, update in-place.

3. **Update `_structure.json`** after structural changes (add/delete sections, figures).

4. **Assemble:** Run `docx_assembler.py`:
   ```
   python <shared-scripts>/docx_assembler.py \
     unpacked/ segments/ revised.docx --original manuscript.docx
   ```

5. **Log operations:**
   - Append to `CHANGES.md`: human-readable description of each change
   - Append to `.applied_ops`: one operation_id per line
   - Append to `_revision_log.md`: timestamp + summary

6. **Flag manual steps** (image insertion, LibreOffice rendering) as TODOs.

**[Long-task check]** After assembly, check context before Phase D. Phase C is typically the heaviest Phase.

---

## Phase D — Verification (delegate to S_RV)

**Input:** `revised.docx` + `segments/` + `_structure.json`

**Output:** `_verification_report.md`

1. Load `S_RV-strategist.md` instructions.
2. Execute 5 verification checks (see S_RV).
3. Write `_verification_report.md` to segments/ directory.
4. Present results to user.
5. If issues found: ask user whether to fix, accept, or undo.

**[Final check]** After Phase D, report completion and present exit options to user:

   修订完成: revised.docx
   验证报告: segments/_verification_report.md

   下一步建议：
   [A] 修订到此结束 —— S_RV 报告已就绪，确认无误即可
   [B] 进入 S7 existing-manuscript —— 做完整评审 + 语言润色（投稿级打磨）
   
   S7 入口会读取 _revision_log.md 中的 modified_sections 字段，
   聚焦审查修改过的章节，避免全文重审的开销。

---

## Long-Task Protection

Check context length after each Phase (A/B/C/D). If remaining capacity < 30%:

1. Save current state to `STATE.md`
2. Invoke long-task compression skill
3. On return: re-read STATE.md and continue

This prevents attention drift during multi-phase revision tasks where total context can exceed 50K+ tokens.
