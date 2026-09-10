# Bogda Console S3 影子验收证据

<!-- campus-runner-status:2026-09-10 -->
> 2026-09-10 现状更新：Orchestra/3100 已停用；Y7000 已接入 WSL2、NAS 和 dorm-x86，并发 1，自主 smoke 与 WSL 重启恢复通过。checkpoint key 本地修复已测、尚未部署，DEF-03 未通过现网验收。3101 仍为只读 observer。下文历史设计/操作步骤不代表已经部署；“runner 未到手/未联网/仅雷达停用”等旧状态以[最新交接](../../../docs/reports/2026-09-10-bogda-runner-handoff.md)为准。共享 SQLite 和日志发布接线仍待完成。
<!-- /campus-runner-status -->

- 被测提交：`e2e0974802d0a15687e16079bc5dd5834d638908`
- 分支：`codex/bogda-console`
- 日期：2026-08-24（Asia/Shanghai）
- Profile：`mock-all`
- 公共地址：`http://127.0.0.1:3101`
- BFF：生产构建同源提供；没有启动 3102
- Fixture：六个批准的确定性场景

## 结论

Stage S3 影子验收通过。Prefect 执行状态和 RunResult 科研判断在桌面、平板、
手机及所有异常场景中保持分栏展示；Completed 文案没有表达科研结论成立。
受限提交、取消、schedule/queue 暂停与恢复、追加评审和冲突保留表单均等待权威
回执；评审冲突需明确采用最新 Artifact 后才能再次提交。浏览器没有意外 JS、
React、HTTP 或静态资源错误。

这不是 3100 切换批准，也不包含切换方案。

## 验证矩阵

| 命令 | 结果 |
| --- | --- |
| `py -3.11 -m pytest tests/backend -q` | 77 passed |
| `py -3.11 -m pytest tests/integration/test_local_prefect.py -q` | 1 passed；Prefect 官方本地 test harness，随机端口 |
| `npm run check:contracts` | OpenAPI 与生成的 TypeScript 契约一致 |
| `npm run test:frontend` | 9 files / 33 tests passed |
| `npm run build` | TypeScript 与 Vite production build passed |
| `npm run test:browser` | 84 tests passed，1 worker，约 2.7 分钟 |
| `py -3.11 -m pytest orchestra/console/tests -q`（仓库根目录） | 99 tests passed |
| `git diff --check` | 无 whitespace error |

axe-core 在总览、运行列表、评审、运行详情/评审表单、基础设施和降级态上运行；
serious/critical violations 为 0。键盘验收覆盖 skip link、对话框初始焦点、Tab
圈定、Escape 和焦点恢复，并启用 reduced-motion 模拟。

## 响应式矩阵

| Project | Viewport | 基础重排 | 200% 等效重排 | axe | 交互 |
| --- | --- | --- | --- | --- | --- |
| `desktop-1440` | 1440×900 | 通过 | 720px CSS viewport 通过 | 通过 | 通过 |
| `desktop-1280` | 1280×800 | 通过 | 640px CSS viewport 通过 | 通过 | 通过 |
| `tablet-768` | 768×1024 | 通过 | 384px CSS viewport 通过 | 通过 | 通过 |
| `phone-390` | 390×844 | 通过 | 320px 最小 CSS viewport 通过 | 通过 | 通过 |
| `phone-360` | 360×800 | 通过 | 320px 最小 CSS viewport 通过 | 通过 | 通过 |
| `phone-320` | 320×800 | 通过 | 320px 最小 CSS viewport 通过 | 通过 | 通过 |

每个项目均断言 `document.documentElement.scrollWidth <= window.innerWidth`。

## 场景覆盖

- `normal-active`：四页导航、执行/科研分离、Deployment 提交、取消、评审追加、
  schedule/queue 暂停与恢复、compute。
- `sleep-queued`：Worker OFFLINE、sleep、排队状态。
- `gaming-paused`：gaming、原始 Prefect Paused 状态。
- `degraded-stale`：Prefect 无 last-good 时明确 503/错误面板。
- 浏览器内精确响应 fixture：有 last-good 时显示陈旧来源与来源错误，Power 陈旧但
  不推断 Worker 状态。
- `result-missing-invalid-conflict`：缺失、最新无效仍权威、maintenance；另以精确
  409 fixture 验证冲突表单保留。
- `mobile-dense`：窄屏高密度运行与 200% 等效重排。

Power Agent 始终显示“模拟数据”。四种模式 sleep、compute、gaming、maintenance
均已覆盖。dorm-x86 的 CPU/GPU 队列始终共享工作池并发 1。

## 截图

- [桌面总览](overview-desktop.png)
- [桌面运行详情](run-detail-desktop.png)
- [手机科研评审](scientific-review-phone.png)
- [手机基础设施降级态](infrastructure-degraded-phone.png)

## 端口与回退

验收开始前只读请求 `http://127.0.0.1:3100/`：HTTP 200。验收结束后同一只读
请求：HTTP 200。Playwright 只启动任务拥有的 3101 进程，结束后 3101 无监听。
浏览器测试还断言所有同源请求的端口集合精确等于 `{3101}`。

旧控制台与 Orchestra 数据仍是回退路径；没有停止、覆盖或修改 3100 路由。

## 明确未触碰

- Pi 和 Pi 部署
- 真实 dorm-x86、Power Agent 或电源模式
- `bogda/` 核心
- `orchestra/console/` 产品文件
- Orchestra 数据
- 真实 Prefect 写操作或 Worker 执行
- 3100 进程、监听与路由

集成测试只使用 Prefect 官方本地临时服务、临时 SQLite 和随机端口，不启动
Worker、不执行 Flow。
