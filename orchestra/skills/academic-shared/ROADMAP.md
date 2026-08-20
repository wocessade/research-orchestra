# ROADMAP — Academic Writing Skill Group

Generated: 2026-06-27 (Mission 009 — 分享前全面审查收敛后)
Proposed by: Agent G innovation audit

## P1 (推荐即时实施)

### 1. reporting-standards/ 接线
- **领域**: shared/reporting-standards/ 的 PRISMA/CONSORT/STROBE 零引用
- **影响**: S2-LR (文献综述) 质量门缺少核心参考文件
- **关键动作**:
  - journal manifest.yaml references: 添加 prisma-2020.md, condition: stage[S2-LR]
  - S2-LR strategist 添加显式 PRISMA 加载指令
  - standards-detector.md 扩展支持 CONSORT/STROBE
- **工作量**: S (约30分钟)

### 2. style_learning/ pipeline 接入
- **领域**: thesis 和 journal 的 style_analyzer.py/style_extractor.md 存在但未接入
- **影响**: 核心"提取-应用"循环断裂
- **关键动作**:
  - journal manifest.yaml references: 注册 style_extractor.md, condition: stage[S1]
  - S1 strategist 更新: 用户提供写作样本时调用提取器
  - 创建 style_profiles/default-academic-zh.json 示例配置
- **工作量**: M (约1小时)

## P2 (推荐后续实施)

### 3. commands/ 系统接线
- **领域**: shared/commands/ 的 check-refs/de-ai/latex-cleanup/verify-math 零引用
- **关键动作**:
  - 三模块 manifest.yaml references: 注册4个命令, 按条件加载
  - 相关 strategist 添加 "### Tool Commands" 引用段
- **工作量**: S

### 4. GLOSSARY.md 跨模块部署
- **领域**: 仅 coursework 有 GLOSSARY.md
- **关键动作**:
  - academic-shared/ 创建规范术语表 (提取 coursework 的14概念)
  - 各模块 README/SKILL.md 引用共享版
- **工作量**: S

### 5. checkpoint/state_manager.py 接入
- **领域**: thesis 有断点续写代码但未接入 pipeline
- **关键动作**:
  - manifest.yaml 注册 state_manager.py, condition: stage[T4]
  - T4 strategist 添加章节级 checkpoint 保存指令
- **工作量**: M

## P3 (低优先级/维护)

### 6. journal skills-embedded 清理
- **领域**: 4个孤立文件 (nature-paper2ppt/pptx/scientific-slides)
- **关键动作**: sync-to-modules.py 添加跳过列表
- **工作量**: S

---

## 实施原则
1. **条件加载优先**: 新引用必须使用 manifest condition/stage 守卫, 不在 always_load 中膨胀上下文
2. **先参考后执行**: 命令类文件先注册为 on_demand reference, 非 always_load
3. **每项完成后跑 validate_pipeline.py 确认一致性

## Done (2026-07-27)

### LaTeX + Plotting canonical skills
- Added sibling skills `academic-latex` and `academic-plotting`; embedded routers updated; journal S4/S5 wired.
- Remaining: optional thesis/coursework strategist Mentions; run `sync-to-modules.py --component skills-embedded` after pull.

## Done (2026-07-27 evening — completeness pass)

### Coursework latex/plotting parity
- Expanded coursework skills-embedded allowlist; manifest `writingFormat` + sibling refs; C3 format routing.

### Bib bridge + smoke
- `literature/bib_to_bibliography.py`; `SMOKE-LATEX-PLOTTING.md`; check-refs documents bib→json.

### Commands + gates
- S4/S6/S7/S8 + T4 Tool Commands wired; thesis manifest commands + checkpoint; gate-chain Q5/QC3 tightened; control-char corruption fixed; sync static-core.

## Done (2026-07-27 — P0 from external skill audit)

### Contribution gate + CS conference path
- confirmed_contribution + contribution_check; Draft0/Final Intro; Results Takeaway map
- Wired into journal S3/S4, thesis T1/T4, gate-chain, quick-routing, SKILL.md files

## Done (2026-07-27 — P1)

### Issues + rewrite matrix + citation support bank
- validate_issues / results-backfill; rewrite_matrix; citation_support_bank
- Strategists S2/S4/S6/S7 + T2/T6; gates; routing; SKILL.md

## Done (2026-07-27 — Research Engine)

### academic-research-engine sibling skill
- RQ→H→EXP/NEG→Ci→ISS→CLM schemas; experiment cards; radar routing docs; handoff_sync
- Wired journal S1/S3 + thesis T1 handoff preload; CHANGELOG updated
- M4 docs: personas/lab_lead, failure loops, optional tournament, no default GPU

