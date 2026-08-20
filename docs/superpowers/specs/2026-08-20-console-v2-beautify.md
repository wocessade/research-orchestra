# 控制台 v2 美化移交任务书（致 SOL）

- 日期：2026-08-20 · 移交：owner（CC 协调）→ SOL
- 上一阶段：v1 已上线（mission 034，`43fd3a4`，69 unittest 全绿，四页功能验收通过）

## 1. 任务一句话

**把控制台搞好看。** 这是纯前端展示层的美化任务——数据链路、功能、契约全部已就绪且验证过，你的战场是视觉与交互。

## 2. 现状（接手前必读，按序）

1. 使用说明：`orchestra/console/README.md`（组件表/启动方式/降级语义/留言协议）
2. 设计 spec：`docs/superpowers/specs/2026-08-20-console-design.md`（§5 页面结构、§7 留言协议、§8 降级语义）
3. v1 实现：Homepage（gethomepage v2.0.0，app 本体 `D:\Apps\homepage`，不入库）+ 四页配置 `orchestra/console/homepage/`（services/settings/bookmarks/widgets.yaml）+ glue `orchestra/console/`（Python stdlib）
4. 运行方式：`http://127.0.0.1:3000`（Homepage）消费 `http://127.0.0.1:3100`（glue serve 的产物）；refresh 每 10 分钟（schtasks，pythonw 无窗口）

## 3. 数据契约（这是接口，v2 不允许破坏）

glue 产出的 8 个文件在 `orchestra/console/out/`（经 3100 静态服务）：

| 产物 | 形状 | 消费者 |
|---|---|---|
| status.json | 设备展示串（4b/walnut/windows）、queue_len/active_tasks、next[{label,at,in_text}]、recent_tasks、attempts、experiments、degraded/degraded_reason | 状态条/任务实验/系统页 |
| radar.json | available/date/mode/stages/top5/validation/digest_txt | 雷达页 |
| messages.json | latest/pending/alerts 三数组（title/time_text/text） | 留言板 |
| system.ics / personal.ics | RFC5545，floating 本地时间，显式事件实例 | 日历（双层分色） |
| digest.html / messages.html | 全文展示（含 UTF-8 meta） | iframe 全文区 |

改 glue 产出形状 = 破坏契约，必须同步改 69 个测试并说明理由；**本任务默认不动 glue**。

## 4. 自由发挥边界（owner 授权）

- **不局限于 Homepage**：可以换框架（如 Glance、Dashy、自研静态页）、换布局、换配色、改 widget 组合——只要你评估后认为更美更合适，都允许；换框架时 app 本体仍装仓库外（如 `D:\Apps\`），配置/源码入库到 `orchestra/console/` 下
- 视觉风格自由：深色/浅色、信息密度、卡片布局、图表化（如雷达评分趋势）都随你
- 交互增强允许：标签页重排、折叠、倒计时动效等**展示层**交互

## 5. 红线（不可越）

1. **Pi 侧零改动**；只读消费既有端点（GET /api/dashboard、sync_pull）
2. **凭据绝不入库**：ORCHESTRA_MONITOR_TOKEN 等只走环境变量
3. **v1 功能不回退**（验收会逐项核对）：双层日历两色事件、三端状态、雷达阶段时间线+Top5+日报全文、最近 attempt/实验卡、留言/待决/告警（含秒级热重）、降级不报错语义
4. **决策留痕**：审批/派任务仍在对话里做，控制台保持只读（不做写入型功能）
5. 默认绑定 127.0.0.1；v1.5 尾网暴露是后续独立议题，不在本任务
6. 不删除 `orchestra/console/out/` 以外任何既有文件（glue 模块、tests、messages.md 协议格式不动）；新增文件随意

## 6. 验收标准

1. 桌面四页截图（前后对比）：owner 逐页确认"好看"
2. §5 红线第 3 条功能清单逐项核对通过
3. glue 69 个 unittest 保持全绿（未动 glue 则直接跑 `python -m unittest discover tests` 于 `orchestra/console/`）
4. 部署说明更新到 `orchestra/console/README.md`（若替换了框架/启动方式）
5. commit 无署名行（项目红线）；提交后可 push 或留 commit 待 owner 验收

## 7. 对 SOL 的协作提示（owner 点名）

**你写代码偏过度谨慎，这个任务请反过来做：**
- 这是**纯展示层**美化，界面优先、视觉优先、大胆尝试；不要在 glue/数据契约上堆防御性代码（它们已验证并有测试兜底）
- YAGNI 从严：不做的功能=不做；防御分支只在真实接触面出现时加
- 改动面越小越稳：能只动配置就只动配置；评估换框架时优先问"配置层改造够不够"
- 交付前自检截图；拿不准的视觉方向可以一次给 2 个方案，不必十全十美

## 8. 交接检查点

- 开始前：把 §2 四份材料读完再动手
- 完成时：给 owner 四页前后截图 + 改动清单 + 验收自评（§6 五条逐条打勾）
