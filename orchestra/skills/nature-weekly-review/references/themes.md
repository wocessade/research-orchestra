# Themes — 6 套配色方案

每次生成时随机选取一个主题名，写入 HTML `<html data-theme="...">`。所有颜色通过 CSS 变量定义，Chart.js 也读取 `--chart-N` 变量。

## 代理操作指南

生成 HTML 时：
1. 随机取 `Math.floor(Math.random() * 6)` 索引
2. 将对应主题名写入 `<html data-theme="...">`
3. 在 `<style>` 中根据 `data-theme` 设置所有 CSS 变量
4. Chart.js 创建前用 `getComputedStyle(document.documentElement)` 读取 `--chart-1`~`--chart-5`

## 主题定义

### 1. academic-clean (亮色·蓝白)

```
--bg: #f8fafc
--bg-card: #ffffff
--text: #1e293b
--text-secondary: #64748b
--border: #e2e8f0
--accent: #2563eb
--accent-light: #dbeafe
--chart-1: #2563eb
--chart-2: #0891b2
--chart-3: #7c3aed
--chart-4: #ea580c
--chart-5: #059669
--badge-A: #166534
--badge-A-bg: #dcfce7
--badge-B: #1e40af
--badge-B-bg: #dbeafe
--badge-C: #92400e
--badge-C-bg: #fef3c7
--badge-D: #6b21a8
--badge-D-bg: #f3e8ff
--badge-E: #9ca3af
--badge-E-bg: #f3f4f6
--sidebar-bg: #1e293b
--sidebar-text: #cbd5e1
--sidebar-active: #2563eb
```

### 2. warm-amber (亮色·暖琥珀)

```
--bg: #fffbeb
--bg-card: #ffffff
--text: #1c1917
--text-secondary: #78716c
--border: #f5d0a9
--accent: #d97706
--accent-light: #fef3c7
--chart-1: #d97706
--chart-2: #dc2626
--chart-3: #7c2d12
--chart-4: #b45309
--chart-5: #92400e
--badge-A: #166534
--badge-A-bg: #dcfce7
--badge-B: #1e40af
--badge-B-bg: #dbeafe
--badge-C: #92400e
--badge-C-bg: #fef3c7
--badge-D: #6b21a8
--badge-D-bg: #f3e8ff
--badge-E: #9ca3af
--badge-E-bg: #f3f4f6
--sidebar-bg: #292524
--sidebar-text: #d6d3d1
--sidebar-active: #d97706
```

### 3. forest-green (亮色·森林绿)

```
--bg: #f0fdf4
--bg-card: #ffffff
--text: #052e16
--text-secondary: #4b5563
--border: #bbf7d0
--accent: #059669
--accent-light: #d1fae5
--chart-1: #059669
--chart-2: #16a34a
--chart-3: #0284c7
--chart-4: #d97706
--chart-5: #7c3aed
--badge-A: #166534
--badge-A-bg: #dcfce7
--badge-B: #1e40af
--badge-B-bg: #dbeafe
--badge-C: #92400e
--badge-C-bg: #fef3c7
--badge-D: #6b21a8
--badge-D-bg: #f3e8ff
--badge-E: #9ca3af
--badge-E-bg: #f3f4f6
--sidebar-bg: #064e3b
--sidebar-text: #a7f3d0
--sidebar-active: #059669
```

### 4. dark-slate (暗色·深蓝灰)

```
--bg: #0f172a
--bg-card: #1e293b
--text: #e2e8f0
--text-secondary: #94a3b8
--border: #334155
--accent: #38bdf8
--accent-light: #0c2d48
--chart-1: #38bdf8
--chart-2: #818cf8
--chart-3: #f472b6
--chart-4: #fbbf24
--chart-5: #34d399
--badge-A: #4ade80
--badge-A-bg: #052e16
--badge-B: #60a5fa
--badge-B-bg: #172554
--badge-C: #fbbf24
--badge-C-bg: #422006
--badge-D: #c084fc
--badge-D-bg: #2e1065
--badge-E: #9ca3af
--badge-E-bg: #1f2937
--sidebar-bg: #020617
--sidebar-text: #94a3b8
--sidebar-active: #38bdf8
```

### 5. deep-teal (暗色·深青)

```
--bg: #042f2e
--bg-card: #115e59
--text: #ccfbf1
--text-secondary: #5eead4
--border: #0d9488
--accent: #2dd4bf
--accent-light: #134e4a
--chart-1: #2dd4bf
--chart-2: #fbbf24
--chart-3: #f472b6
--chart-4: #818cf8
--chart-5: #fb923c
--badge-A: #4ade80
--badge-A-bg: #052e16
--badge-B: #60a5fa
--badge-B-bg: #172554
--badge-C: #fbbf24
--badge-C-bg: #422006
--badge-D: #c084fc
--badge-D-bg: #2e1065
--badge-E: #9ca3af
--badge-E-bg: #1f2937
--sidebar-bg: #022c22
--sidebar-text: #5eead4
--sidebar-active: #2dd4bf
```

### 6. midnight-plum (暗色·暗紫)

```
--bg: #1a0a2e
--bg-card: #2d1b4e
--text: #f3e8ff
--text-secondary: #c4b5fd
--border: #4c1d95
--accent: #a78bfa
--accent-light: #3b0764
--chart-1: #a78bfa
--chart-2: #f472b6
--chart-3: #38bdf8
--chart-4: #fbbf24
--chart-5: #34d399
--badge-A: #4ade80
--badge-A-bg: #052e16
--badge-B: #60a5fa
--badge-B-bg: #172554
--badge-C: #fbbf24
--badge-C-bg: #422006
--badge-D: #c084fc
--badge-D-bg: #2e1065
--badge-E: #9ca3af
--badge-E-bg: #1f2937
--sidebar-bg: #0d0520
--sidebar-text: #c4b5fd
--sidebar-active: #a78bfa
```

## 侧边栏

所有主题的 sidebar 均为深色底色 + 白色/浅色文字，与主内容区配色独立，确保导航区域始终清晰可读。
