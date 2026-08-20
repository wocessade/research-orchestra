# Stage T_R: 学位论文修订 [Strategist]

**Trigger:** 用户提交修订需求 + 论文源（DOCX 文件 或 thesis_config.yaml + markdown 目录）

**Goal:** 按用户意图修改论文结构/内容/图表，输出修订版 DOCX。

**Path conventions:**
- `<shared-scripts>` = `academic-shared/scripts/revision/`（segmenter, assembler）
- `<docx-scripts>` = docx skill 的 `scripts/office/`（unpack.py, pack.py）

---

## 路径选择

```
输入判断:
  是 .docx 文件？
    → 路径 A：现有 DOCX 修订（segment + assemble，复用 academic-shared 核心脚本）
  是 thesis_config.yaml + thesis_content/？
    → 路径 B：Config 源文件修订（改 config + md → 重新生成）
  其他？
    → 询问用户论文来源
```

---

## 路径 A — 现有 DOCX 修订

**适用场景：** 外部拿到的论文 .docx、之前用其他工具生成的、老师发来的修改稿。

与期刊修订模块相同的 pipeline，区别在论文特有的 heading 检测和结构识别。

### Phase A1 — 分段

1. **Unpack DOCX**
   ```
   python <docx-scripts>/unpack.py thesis.docx unpacked/
   ```

2. **论文版分段**（调用 segmenter 的 `--mode thesis`，自动识别论文标题格式）：
   ```
   python <shared-scripts>/docx_segmenter.py thesis.docx segments/ --mode thesis
   ```

   **识别的论文标题格式：**
   - `第一章 绪论` / `第1章 绪论` → H1
   - `1.1 研究背景` → H2（期刊已有模式）
   - `1.1.1 丝素蛋白结构` → H3（期刊已有模式）
   - `摘要` / `致谢` / `参考文献` / `附录` / `Abstract` → H1

3. **输出节树 + 图/表清单**，用户确认。

**[长期务检查]**

### Phase A2 — 意图捕获 → 执行 → 验证

同 S_R（Phase B→C→D），复用 shared 的 docx_assembler.py 和 S_RV 的 5 项检查。

**差异点：**
- 论文特有的检查项：目录页是否更新、页眉页脚是否一致
- 论文不查引用完整性（学位论文通常数百条参考文献，格式各异）

---

## 路径 B — Config 源文件修订

**适用场景：** 论文是从 T4 pipeline 生成的，有完整的 config + 源文件。

### Phase B1 — 解析当前状态

读取现有的 `thesis_config.yaml`，提取章节结构和图表定义：

```yaml
thesis_structure:
  - type: cover              # 封面（自动生成）
  - type: abstract_cn        # 中文摘要
  - type: abstract_en        # 英文摘要
  - type: toc                # 目录（自动生成）
  - type: chapter
    title: "第1章 绪论"
    sections:
      - title: "1.1 研究背景"
        source: content/chapter1/1.1_background.md
      - title: "1.2 国内外研究现状"
        source: content/chapter1/1.2_literature.md
  - type: chapter
    title: "第2章 材料与方法"
    sections:
      - title: "2.1 材料"
        source: content/chapter2/2.1_materials.md
  - type: acknowledgment     # 致谢
  - type: appendix           # 附录（可选）
  - type: references         # 参考文献
```

### Phase B2 — 意图捕获

接受自然语言修改意图，解析为 config 级别操作：

| 操作类型 | 示例 | 执行方式 |
|---------|------|---------|
| `add_chapter` | "在第3章后加第4章" | 插入 config chapter + 创建源目录 |
| `remove_chapter` | "删掉第5章" | 移除 config entry + 标记源文件 |
| `reorder_chapters` | "把第4章移到第2章前面" | 重排 config 数组 |
| `add_section` | "在3.2后加3.3" | 插入 config section + 新建 .md |
| `remove_section` | "删除2.4节" | 移除 config entry |
| `merge_chapters` | "把第4章并入第3章" | 合并 config entries + 合并 .md |
| `split_chapter` | "把第3章拆成两章" | 分割 config + 创建新 .md |
| `global_replace` | "全文A→B" | 改所有 .md 文件 |
| `add_figure` | "在第3章插入图3-5" | 更新 config + 图编号 |
| `renumber_figures` | "重编号所有图" | 按章节重新编号 |
| `regenerate` | "重新生成DOCX" | 运行 generate_thesis_docx.py |

### Phase B3 — 执行

1. **改 config**：`thesis_config.yaml` 直接编辑
2. **改源文件**：编辑/创建/删除 `.md` 文件
3. **存 checkpoint**：修改前备份原 config（`thesis_config.yaml.bak`）
4. **运行修改后的 generate_thesis_docx.py**：
   ```
   python scripts/generate_thesis_docx.py \
     --config thesis_config.yaml \
     --output revised_thesis.docx
   ```

### Phase B4 — 验证

5 项检查 + 论文特有项：

- **章节完整性**：所有 config 中的 chapter 都对应非空源文件
- **图号连续性**：按"图3-1"格式检查（章节号+序号）
- **交叉引用**："如图3-1所示" → 引用指向存在的图
- **生成无报错**：`generate_thesis_docx.py` 正常退出
- **页码结构**：检查目录→正文→致谢→参考文献的顺序

---

## 长期务保护

同 S_R，每完成一个 Phase 检查上下文长度，不足 30% 时触发压缩后再继续。
