# LaTeX 中文学位论文 (Embedded)

**Source:** `latex-thesis-zh` v5.1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** T4 (Thesis Writing) — Chinese LaTeX thesis writing

## Canonical claim / citation / verify protocol

GB/T layout stays in this file. For claim-evidence engineering, verified BibTeX, and mechanical checks, also load:

- ../../academic-latex/SKILL.md (from this skills-embedded/ file)
- Run: python ../../academic-latex/scripts/verify_paper.py {tex_root} --allow-cjk
- Figures: ../../academic-plotting/SKILL.md

Do **not** invent citations or result numbers. University cls / 封面声明 wording still require user confirmation.


## Capabilities
- 编译诊断 XeLaTeX/LuaLaTeX/latexmk 构建问题
- 检查论文格式、GB/T 7714 参考文献、章节结构、术语一致性
- 审阅逻辑连贯性、文献综述质量、标题表达与 AI 痕迹
- 文献综述重写蓝图：共识 → 分歧 → 局限 → 空白 → 本文切入点
- 在不破坏引用、标签和数学环境的前提下给出修改建议

## Common Commands
```bash
xelatex main.tex
biber main    # or bibtex main for GB/T 7714
xelatex main.tex && xelatex main.tex
latexmk -xelatex main.tex
```

## GB/T 7714 注意事项
- 参考文献格式遵循 GB/T 7714-2015
- 中文文献用中文著录，英文文献用英文著录
- 著者姓名：姓全大写，名缩写（中文: 姓在前名在后）
- 期刊连续页码要标注起止页码
- DOI 可选但建议标注

## GB/T 7714 常见错误修复

### 错误示例：英文文献姓和名未做区分
```bib
@article{smith2020,
  author = {John Smith and Li Zhang},
  ...
}
```
**修复：** 姓全大写，名缩写为字母。GB/T 7714 标准格式：
```bib
@article{smith2020,
  author = {SMITH J and ZHANG L},
  ...
}
```

### 错误示例：中文文献混用英文格式
```bib
@phdthesis{chen2023,
  author = {Chen, Wei and Lee, Ming},
  ...
}
```
**修复：** 中文文献使用中文著录（姓在前，名在后，不缩写）：
```bib
@phdthesis{chen2023,
  author = {陈伟 and 李明},
  ...
}
```

## Anti-Pattern: 混合格式
**症状：** 参考文献列表中，部分条目用 GB/T 7714 格式（[J]、[M]），部分用 APA 格式（(2020).），部分混用。**修复：** 全文献列表统一为 GB/T 7714-2015。中文著录中文条目，英文著录英文条目。不要出现 "[J]. Nature, 2020" 这种中英混杂。

## GB/T 合规清单
- [ ] 参考文献类型标识正确：期刊[J]、专著[M]、学位论文[D]、会议录[C]、标准[S]、电子资源[EB/OL]
- [ ] 英文文献：作者姓全大写、名缩写；中文文献：姓在前名在后
- [ ] 期刊条目包含起止页码（连续页码期刊）
- [ ] 所有条目格式统一（无中英格式混用）
- [ ] `latexmk -xelatex` 或 `xelatex + biber/bibtex` 链无编译错误
