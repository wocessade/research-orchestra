# Command: /latex-cleanup — LaTeX 系统性清理

**来源:** Claude-Scholar 的 `/latex-cleanup` 命令

## 用途

对 LaTeX 论文源文件进行系统性检查与修正。检测常见 LaTeX 错误、不一致的引用、未定义的标签、过期的宏包等。

## 检查清单

### 1. 引用检查
- [ ] 所有 `\cite{}` 有对应 `.bib` 条目
- [ ] 所有 `\ref{}` / `\eqref{}` 有对应 `\label{}`
- [ ] 无重复 label
- [ ] 无未使用的 label

### 2. 编译检查
- [ ] 无未配对的 `\begin{}` / `\end{}`
- [ ] 无丢失的 `$` 定界符
- [ ] 无 undefined control sequence
- [ ] 无 overfull / underfull hbox（如果日志可用）

### 3. 格式检查
- [ ] 图表环境有 caption
- [ ] 所有 `\includegraphics` 文件存在
- [ ] 所有算法/代码环境有 float 包装
- [ ] 章节编号连续

### 4. 引用格式
- [ ] 引用使用 `\citep` / `\citet`（natbib）而不是裸 `\cite`
- [ ] 图形引用使用 `Fig.~\ref{fig:xxx}` 格式
- [ ] 表格引用使用 `Table~\ref{tab:xxx}` 格式
- [ ] 公式引用使用 `Eq.~(\ref{eq:xxx})` 格式

## 运行流程

```
1. 读取主 .tex 文件和所有 \input / \include 文件
2. 运行 latexmk / pdflatex 检查编译错误（如可用）
3. 运行脚本扫描全部 4 个检查清单
4. 输出问题列表（按严重程度排序）
5. 自动修复可自动修正的问题（如 \cite → \citep）
6. 对需要人工判断的问题，标记并给出修复建议
```

## 输出格式

```
── LaTeX 清理报告 ──
严重错误: 0 ✅
警告: 3 ⚠️
  [WARN] main.tex:127 — \ref{fig:accuracy} 未找到对应 \label → 检查拼写
  [WARN] chapter2.tex:45 — 图形文件 figures/result.png 不存在（路径错误？）
  [WARN] references.bib:23 — 条目 "Smith2020" 缺少 year 字段
信息: 5
  [INFO] 发现 3 个裸 \cite 调用 → 已自动替换为 \citep
  [INFO] 发现 2 个未使用的 label → 已删除
```

## 与 academic-latex 的关系

在 checklist 之外，对完整论文树运行机械校验（推荐）：

`ash
python ../academic-latex/scripts/verify_paper.py /path/to/paper
# 中文论文：
python ../academic-latex/scripts/verify_paper.py /path/to/paper --allow-cjk
`

详见 ../academic-latex/references/verification.md 与 citations.md。erify_paper 的 HARD 失败应在宣称编译完成前清除（或由用户显式豁免）。

路径说明：从 cademic-shared/commands/ 出发，../academic-latex 正确；若从某模块的 skills-embedded/ 调用脚本，用 ../../academic-latex/scripts/verify_paper.py。

## 注意

- 建议在最终编译前运行
- 自动修复会备份原文件（加 .bak 后缀）
- 不修改 LaTeX 的内容/语义，只修复格式和引用问题
