# HTML Template Spec — 8 个 Section 的详细结构

模板文件：`templates/weekly-report.html`

## 数据注入点

模板顶部 `<script id="weekly-data" type="application/json">WEEKLY_DATA_PLACEHOLDER</script>` — agent 替换 `WEEKLY_DATA_PLACEHOLDER` 为实际 JSON。

## 全局结构

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="THEME_NAME">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ISO年}第{W}周 文献周报</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>/* 所有 CSS，使用 var(--*) */</style>
</head>
<body>
  <nav id="sidebar"><!-- 侧边栏导航 --></nav>
  <main>
    <section id="cover"><!-- ① 封面 --></section>
    <section id="overview"><!-- ② 本周概览 --></section>
    <section id="table"><!-- ③ 文献总表 --></section>
    <section id="a-papers"><!-- ④ A类重点 --></section>
    <section id="comparison"><!-- ⑤ 跨论文对比 --></section>
    <section id="clusters"><!-- ⑥ 主题聚类 --></section>
    <section id="critique"><!-- ⑦ 批判与空白 --></section>
    <section id="next-week"><!-- ⑧ 下周计划 --></section>
  </main>
  <script>/* 数据渲染 + 图表 + 导航 */</script>
</body>
</html>
```

## Section ① 封面

```
┌──────────────────────────────────────────┐
│           2026年 第27周                   │
│          文献研究周报                      │
│          06/30 — 07/06                   │
│                                          │
│    📄 N 篇     ⭐ 均分 X.X     🏅 A类 N   │
│                                          │
│    [分数分布柱状图]                        │
└──────────────────────────────────────────┘
```

## Section ② 本周概览

```
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ 总论文  │ │ 平均分  │ │ 中位数  │ │ A 类   │
│   5    │ │  7.3   │ │  7.5   │ │   2    │
└────────┘ └────────┘ └────────┘ └────────┘

┌──────────────────┐  ┌──────────────────┐
│  分数分布(柱状图) │  │  分类分布(饼图)   │
└──────────────────┘  └──────────────────┘
```

卡片使用 `<div class="stat-card">`，大号数字 + 小号标签。

## Section ③ 文献总表

可排序表格，列：标题 | 分数 | 分类 | 标签 | Obsidian 链接

```html
<table id="paper-table">
  <thead>
    <tr>
      <th data-sort="title">标题</th>
      <th data-sort="score">⭐ 评分</th>
      <th data-sort="class">分类</th>
      <th>标签</th>
      <th>链接</th>
    </tr>
  </thead>
  <tbody><!-- JS 渲染 --></tbody>
</table>
```

点击表头排序。分类列显示彩色 badge。标题列有 `data-placeholder` 属性标记待精读论文。

## Section ④ A类重点论文

```html
<div class="a-paper-card">
  <div class="card-header">
    <h3>论文标题</h3>
    <span class="badge badge-A">A_核心主线</span>
    <span class="badge badge-placeholder">⚠️ 待精读</span> <!-- 条件渲染 -->
  </div>
  <div class="card-body">
    <div class="field"><strong>核心主张：</strong><span>...</span></div>
    <div class="field"><strong>方法：</strong><span>...</span></div>
    <div class="field"><strong>关键发现：</strong><span>...</span></div>
    <div class="field"><strong>Connection to Research：</strong>
      <!-- TODO: 研究方向 --> <!-- 后补占位符 -->
    </div>
    <div class="field"><strong>下一步：</strong><span>...</span></div>
  </div>
</div>
```

条件：
- 有 A 类 → 渲染 A 类卡片（score 降序）
- 无 A 类 → 显示"本周无 A_核心主线 论文，以下为本周最高分论文" + top-3 卡片
- 待精读占位符 → 添加 `badge-placeholder`

## Section ⑤ 跨论文对比

```html
<h2>方法对比</h2>
<table class="comparison-table">
  <!-- 5 列: 论文 / 方法/架构 / 训练策略 / 数据集 / 关键创新 -->
</table>

<h2>指标对比</h2>
<table class="comparison-table">
  <!-- 5 列: 论文 / 主要指标 / 基准/基线 / 提升 / 备注 -->
</table>
```

若仅 1 篇论文 → 显示占位文字。

## Section ⑥ 主题聚类

```html
<canvas id="chart-tags" height="300"></canvas>
<div class="theme-clusters">
  <h3>主题分组</h3>
  <!-- agent 生成的文字分析 -->
</div>
```

## Section ⑦ 批判与空白

```html
<div class="critique-categories">
  <div class="critique-cat">
    <h4>代码/复现</h4>
    <ul><li>...</li></ul>
  </div>
  <!-- 6 个类别 -->
</div>
<div class="research-gaps">
  <h3>研究空白</h3>
  <!-- agent 从局限中综合的研究空白 -->
</div>
```

## Section ⑧ 下周计划

从所有论文的 "下一步" section 聚合，去重后渲染为 checklist：

```html
<ul class="next-checklist">
  <li><input type="checkbox"> 精读 Paper X</li>
  <li><input type="checkbox"> 复现 Paper Y 的方法</li>
</ul>
```

## 侧边栏导航

```html
<nav id="sidebar">
  <div class="sidebar-title">{YYYY}年第{W}周</div>
  <ul>
    <li><a href="#cover" class="active">📋 封面</a></li>
    <li><a href="#overview">📊 概览</a></li>
    <li><a href="#table">📋 文献总表</a></li>
    <li><a href="#a-papers">⭐ A类论文</a></li>
    <li><a href="#comparison">🔬 跨论文对比</a></li>
    <li><a href="#clusters">🏷️ 主题聚类</a></li>
    <li><a href="#critique">💬 批判与空白</a></li>
    <li><a href="#next-week">📝 下周计划</a></li>
  </ul>
</nav>
```

IntersectionObserver 监听 main 中的 section，高亮对应侧边栏链接。

## CSS 响应式

```css
@media (max-width: 768px) {
  #sidebar {
    position: relative;
    width: 100%;
    height: auto;
    padding: 12px;
  }
  #sidebar ul {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  main {
    margin-left: 0;
  }
}
```

## 打印样式

```css
@media print {
  #sidebar { display: none; }
  canvas { max-width: 100%; page-break-inside: avoid; }
  .stat-card, .a-paper-card { page-break-inside: avoid; }
  body { font-size: 11pt; }
}
```
