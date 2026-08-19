# 双面板设计备忘

> 决策日期: 2026-07-26 · 状态: 已锁定，开始实现  
> **2026-08 更新：CC hooks / windows-reporter 已停用**；双面板逻辑仍在代码中，无上报时保持默认闲置面板，DeepSeek 用量抓取不受影响。

## 目标

按 Claude Code 状态自动切换两套墨水屏布局：

| 面板 | 触发 | 专注 |
|------|------|------|
| **活跃** | `running` / `waiting` | 编程工作 |
| **闲置** | `idle`（立刻切换） | 桌面信息 |

`error` / `compact-warning`：保持当前面板类型，仅更新 LED / 上下文等字段（不单独第三套布局）。

## 刷屏策略

- **切换面板** → `display_Base` 全刷（版面结构变了）
- **同面板内**小变化 → 全幅局刷波形（现有 `PARTIAL_REFRESH_ENABLED`）
- 强制全刷周期不变（30min）

## 活跃面板内容

1. 标题栏：品牌 + CC 状态 + 时钟  
2. DeepSeek：**余额（¥）**、本期/累计消费、请求数（平台抓取）  
3. 模型用量条（DeepSeek platform）  
4. **上下文窗口 %**（来自 CC hooks stdin，非启发式）  
5. **本会话**：Claude 费用（**USD $**）+ 时长 + 轮次  
6. 底栏：更新时间 / 延迟 / 服务健康  

货币规则：**DeepSeek ¥ 与 Claude $ 分开展示，不混算、不换汇。**

## 闲置面板内容

1. 标题栏：品牌 + `空闲` + 时钟 + **日期/星期**  
2. **南京天气**（wttr.in，刷新间隔 15–30min）  
3. DeepSeek 速览：余额 + 本期消费 + 请求数  
4. **上一会话摘要**：Claude `$` / 时长 / 峰值上下文%（`session_end` 后保留至下次 `session_start`）  
5. 服务状态行  

**暂缓：** Windows CPU/温度/内存心跳；Pi 负载/温度。

## 数据流

```
CC hooks → reporter.py
  - argv: status / session_start / session_end
  - stdin JSON (CC 提供): cost.total_cost_usd, context_window.*, session_id, model
  → POST /api/status

Pi app.py
  - 更新 state.cc_* / session_*
  - panel = active if status in (running,waiting) else idle
  - eink.render(state)  // 面板变化 → 全刷

Pi 定时
  - balance 60s / usage 300s / weather ~20min / eink check 30s
```

### reporter stdin 字段（参考 ccusage statusline）

```json
{
  "session_id": "...",
  "cost": { "total_cost_usd": 0.85 },
  "context_window": {
    "total_input_tokens": 125000,
    "context_window_size": 200000
  },
  "model": { "display_name": "..." }
}
```

`context_percent = round(100 * total_input_tokens / context_window_size)`（缺省则不改旧值）。

### 会话用量生命周期

| 事件 | 行为 |
|------|------|
| `session_start` | 清零 session cost/时长起点/峰值 context；开始新会话 |
| 会话中 hooks | 更新 cost、context%、可选 bump round |
| `session_end` | 冻结摘要到 `last_session`；活跃字段可清零或保留至下次 start |
| 闲置面板 | 读 `last_session` 展示 |

## 配置

```python
WEATHER_CITY = "Nanjing"
WEATHER_INTERVAL = 1200  # 20 min
```

## 实现顺序

1. `reporter.py` 读 stdin + 上报新字段  
2. `app.py` / `config.py` 扩展 state、对齐面板切换 → 强制全刷  
3. `eink_dashboard.py` 活跃/闲置两套 `_draw_*`  
4. `weather.py`（wttr.in）+ scheduler  
5. 部署与 hooks 说明（stdin 需 hooks 把 JSON 管给 reporter）

## 非目标（本轮）

- Windows 系统监控心跳  
- Pi thermal/load 主展示  
- 多 zone 局刷裁剪  
- 货币汇率换算  
