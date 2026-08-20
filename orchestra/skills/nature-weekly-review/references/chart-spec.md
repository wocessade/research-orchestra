# Chart.js 图表配置

## CDN

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

## 通用配置

所有图表使用以下全局默认值：

```javascript
Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim();
Chart.defaults.borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = true;
```

## 图表 1: 分数分布柱状图 (Section ① 封面 + ② 概览)

```javascript
{
  type: 'bar',
  data: {
    labels: ['0-5', '5-6', '6-7', '7-8', '8-10'],
    datasets: [{
      label: '论文数',
      data: [/* bucket values */],
      backgroundColor: chartColors, // getComputedStyle --chart-1~5
      borderRadius: 6,
      borderSkipped: false,
    }]
  },
  options: {
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } },
      x: { grid: { display: false } }
    }
  }
}
```

## 图表 2: 分类分布饼图 (Section ② 概览)

```javascript
{
  type: 'doughnut',
  data: {
    labels: ['A_核心主线', 'B_章节支撑', 'C_工程背景', 'D_方法借鉴', 'E_暂存低优先'],
    datasets: [{
      data: [/* class counts */],
      backgroundColor: ['--badge-A-bg色', '--badge-B-bg色', '--badge-C-bg色', '--badge-D-bg色', '--badge-E-bg色'],
      borderColor: ['--badge-A色', ...],
      borderWidth: 2,
    }]
  },
  options: {
    plugins: {
      legend: { position: 'bottom' }
    }
  }
}
```

## 图表 3: 标签频率横向柱状图 (Section ⑥ 主题聚类)

```javascript
{
  type: 'bar',
  data: {
    labels: [/* tag names, Top 15 */],
    datasets: [{
      label: '出现次数',
      data: [/* tag counts */],
      backgroundColor: accentColor,
      borderRadius: 4,
    }]
  },
  options: {
    indexAxis: 'y',  // horizontal
    plugins: { legend: { display: false } },
    scales: {
      x: { beginAtZero: true, ticks: { stepSize: 1 } },
      y: { grid: { display: false } }
    }
  }
}
```

## 图表颜色读取

生成 HTML 时，直接在 JS 中读取 CSS 变量：

```javascript
const style = getComputedStyle(document.documentElement);
const chartColors = [
  style.getPropertyValue('--chart-1').trim(),
  style.getPropertyValue('--chart-2').trim(),
  style.getPropertyValue('--chart-3').trim(),
  style.getPropertyValue('--chart-4').trim(),
  style.getPropertyValue('--chart-5').trim(),
];
const accent = style.getPropertyValue('--accent').trim();
```

这样更换主题时图表自动跟随，无需修改 JS 代码。
