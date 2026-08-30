# Bogda Stage E 开工

日期：2026-08-30

owner 授权：Stage E；官方余额 API；「执行」+ **测试花费 ≤10 CNY 不必再问**

**不是 Gate 6 / Gate 7 通过。** 不是 3100 切换。不是 `dorm-x86`。RK3528 上 trial `20260830T034154Z` 观察窗内 **不** 往 `pi-service` 丢研究 Flow。

计划：[`docs/superpowers/plans/2026-08-30-bogda-stage-e.md`](../superpowers/plans/2026-08-30-bogda-stage-e.md)

## owner 拍板（2026-08-30）

- **生产自动审批上限 20 CNY**（3101 前台；超出人工批）。
- **测试/冒烟 ≤ 10 CNY** 不必再问。本轮实测远低于此。
- **只读余额：** 官方 `GET https://api.deepseek.com/user/balance`。核桃派 dashboard 只给墨水屏。
- **9.8 切网：** URL 不变；校园网能否出网另测。

## 环境变量 / 凭据（值永不入库 / 不入口头）

| 名 | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | 官方余额 + 付费调用。本机 Windows User env **未设**；live smoke 读 dsh 凭据库，不打印。 |
| `ORCHESTRA_MONITOR_TOKEN` / `MONITOR_TOKEN` | 仅墨水屏。Bogda 准入不依赖。 |

## 已做

| Task | 内容 |
|---|---|
| 1 | `SqliteBudgetLedger` |
| 2 | paid-call + SQLite + fake executor |
| 3 | `DeepSeekBalanceClient` 契约测试；**2026-08-30 live GET 成功**（`available=true`，CNY，`source_status=up`，余额 **41.81**） |
| 4 | 本机 Flash + Pro dsh headless 各一次，stdout 均为 `pong`。未打 RK3528 worker |

Windows 修复：`SubprocessCommandRunner` 用 `shutil.which`，否则 uv/Python 对裸 `dsh` 是 `FileNotFoundError`。

## live smoke 数字（2026-08-30 约 13:53 北京）

- 调用前后余额都是 **41.81 CNY**（接口两位小数，delta `0.00`）
- 目录保守估：Flash `0.021` + Pro `0.063` = **0.084 CNY**（按 8k miss + 2k out；实际更小）
- dsh **不写** `usage.json`，适配器记 `usage_unknown`（符合现契约；DEF-02 精确对账未关）
- 产物在 `D:\Temp\bogda-stage-e-smoke\`，不入库

## 明确还没做

| 项 | 原因 |
|---|---|
| dsh → Bogda `usage.json` 桥 | live 已证明 argv；精确 CNY 仍缺 |
| 3101 real profile 接余额 | 客户端已 live 通 |
| 真 Prefect suspend/resume | 不占用 Gate 6 现网 worker |
| 3101 真写入 S1/S2 | 另开口 |
| 产物保留策略 DEF-13 | 后续 task |
| 20 CNY 自动审批写进 `BudgetGuard` | 政策已定；执行码尚未加 |

Gate 6 观察窗内仍不往 RK3528 worker 丢付费 Flow。
