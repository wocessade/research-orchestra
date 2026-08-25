# 雨课堂考试放出监控（exam-watch）设计

日期：2026-08-25
状态：设计定稿

## 定位

用户需要监控雨课堂课程「2026秋-新生入学教育-2026」（classroom_id=25631011，考核方案中考试占 50%）的**考试什么时候放出来**，10 分钟轮询一次，发现后控制台留言 + QQ 邮件双重提醒。脚本挂 4B（常驻 Linux、7×24）。

## 背景探索结论（2026-08-25 实测）

- 目标 URL `changjiang.yuketang.cn/v2/web/studentLog/25631011?...` 是纯 SPA 壳（6.4KB，有无 cookie 逐字节相同），考试数据全部来自 JSON API
- 页面「考试（ 0个学习单元 ）50%」的直接数据源是考核方案接口：
  `GET /c27/online_courseware/evaluation/score_setting/get_sku_evaluation_list_readonly/12651805/`
  其中 `evaluation_tag_list[]` 的「考试」条目（id=12）当前 `use_count=0`、`score_proportion=0.5`
- 第二重信号：课程学习内容接口
  `GET /mooc-api/v1/lms/learn/course/chapter?cid=25631011`
  的 `course_chapter[].section_leaf_list[].leaf_type`；SPA 源码确认 **leaf_type=5 = 考试**（lms-exam，路由 `5===leaf_type?...name:"lms-exam"`），当前全为 7（课件）
- 其他候选已排除：`/v2/api/web/exams/` 返回 uid→userId 映射而非列表；`/v/rain_exam/get_upcoming_exam/` 是首页「本周考试」入口（当前 `data:[]`）；mooc-api exam 列表端点 404
- 认证配方（已用纯 requests 复现 200）：cookie（sessionid 等）+ 请求头 `x-csrftoken`（=cookie 中 csrftoken 值）、`uv-id`、`classroom-id`、`university-id`、`xt-agent: web`、`xtbz: ykt`、Chrome UA；缺 `x-csrftoken`/`uv-id`/`classroom-id` 等任一即 401

## 架构

```
4B（常驻）                          Windows（控制台）
exam-watch.timer ─每10min→ exam-watch.service (oneshot)
                          └─ broker/exam_watch.py
                              ├─ 读 cookie broker-data/exam_cookie.txt
                              ├─ 轮询 2 个 API（双信号）
                              ├─ 状态 broker-data/exam_watch_state.json（幂等，防重复）
                              ├─ 首次变化：写 results/exam_alert.json
                              │             + 调 /usr/local/bin/send_email.py 发 QQ 邮件
                              └─ 达到目标（考试放出）后停止轮询
                                              │
                    console refresh 每10min sync_pull（已有链路）
                                              ▼
                              console: feed_exam.py 读 results/exam_alert.json
                                        → append_alert（messages.md「最新」栏）
```

- 复用现有链路：4B `send_email.py`（已在 /usr/local/bin，SMTP 凭据走 systemd env conf）与 console `sync_pull`（`OrchestraConsoleRefresh` 每 10 分钟拉 results）
- 通知文件走 `broker-data/results/exam_alert.json` 是因为 sync_pull 只拉 results/ 与 logs/ 两个目录，零新增同步链路

## 组件

### 1. `broker/exam_watch.py`（stdlib only）

- 参数：`--classroom-id 25631011 --sku-id 12651805 --cookie-file /home/liuxfs/broker-data/exam_cookie.txt --state-file .../exam_watch_state.json --alert-file .../results/exam_alert.json`（默认值即 4B 部署路径，本机测试可覆盖）
- 每轮：
  1. 读 cookie 文件（HTTPS 视作凭据，日志只记路径不记内容）
  2. GET 考核方案接口 → 提取「考试」条目 `use_count`
  3. GET course/chapter → 统计 `leaf_type=5` 叶子数
  4. 两个信号取**任意一个 >0** 即判定「考试放出」
  5. 判定变化比对上轮 state：`0→N` 首次触发；重复运行不重复通知（状态文件记 `exam_found: true` 后即静默退出）
- 发现考试细节：从 chapter 接口摘考试叶子 `name` / chapter 信息；考务详情字段不全时告警文案只写「考试已放出，请登录雨课堂查看」+ 已确认的叶子名
- 考试条目按 `name=="考试"` 提取（不回退 name 匹配时报 0；id 是产品内部号，name 是用户可见语义）
- HTTP：`urllib.request` + Cookie 头 + 上述请求头；超时 15s；捕获网络错误 → 写 state 的 `last_error`，静默重试不告警（下一轮自然恢复）；**401/`Authentication credentials were not provided`** → 写告警「雨课堂 cookie 已过期，请重新导出并上传 4B」到 alert 文件 + 邮件，随后停止轮询（避免每 10 分钟重复邮件；恢复需用户换 cookie 后删 state 文件重来）
- 退出码：0=OK 或告警已发；1=脚本出错（systemd 会记日志）
- 到达目标（考试放出 + 通知完成）后正常退出 0；下一次 timer 唤醒时读 state 判定已完成，静默退出

### 2. `broker/orchestra-exam-watch.timer` + `.service`（Type=oneshot）

- timer：`OnBootSec=10min` + `OnUnitActiveSec=10min`（开机 10 分钟补首检，之后每 10 分钟）；`Persistent=true`（错过多次唤醒追上最近一次）；Timezone/Format 对齐 `orchestra-timer.timer`
- service：`ExecStart=/usr/bin/python3 /home/liuxfs/broker/exam_watch.py`，`User=liuxfs`，`StandardOutput=journal`；`EnvironmentFile=/etc/systemd/system/orchestra-broker.service.d/env.conf`（SMTP 凭据；send_email.py 从自身进程环境读 `SMTP_USER`，同环境文件方案与现网 backup 告警链路一致，env.conf 缺失时脚本按「邮件跳过」降级，不崩溃）
- 首次部署：随 `deploy_broker.sh` 传载（/tmp → /etc/systemd/system，enable --now）

### 3. `console/feed_exam.py`（stdlib only）

- `parse_exam_alert(path) -> dict | None`：读 `results/exam_alert.json`，字段：`exam_found`、`exam_names`、`leaf_count`、`use_count`、`found_at`、`source`、`alerted`（是否已通知）；文件缺失/JSON 非法 → None（refresh 降级）
- `merge_exam_alert(human, exam_alert, messages_text)`：告警存在且 `exam_found=true` 且 `messages.md` 中尚无该 `found_at` 标记 → 插入「最新」栏；否则原样返回
- `append_exam_marker(messages_path, exam_alert)`：把「雨课堂：考试已放出（x个）——〔叶子名〕」以 `- 考试：` 前缀行写入 messages.md（幂等：写前检查 `found_at` 已存在则跳过；行内注明 scp 后回看控制台）
- `console_feed.py cmd_refresh` 增加一步：`exam_alert = parse_exam_alert(results_root / "exam_alert.json")` → 优先 `append_exam_marker`（写文件持久）再 merge 进「最新」栏
- 目标：控制台 3100「最新」栏出现一条「雨课堂：考试已放出（x个）——〔叶子名〕」，不会每次 refresh 重复刷；4B 上 `results/exam_alert.json` 经由 sync_pull 拉回本地 `orchestra/results/exam_alert.json`

### 4. `deploy_broker.sh` 增量

- 传载 `broker/exam_watch.py` → `/home/liuxfs/broker/`
- 传载两个 unit → /tmp → 远端 sudo mv 到 /etc/systemd/system/ → `systemctl enable --now orchestra-exam-watch.timer`
- `sed REMOTE_ROOT` 路径改写（alert 文件、cookie 路径不写死在脚本内，用默认参数值 + 环境覆盖）

### 5. 凭据

- cookie 文件：`/home/liuxfs/broker-data/exam_cookie.txt`（chmod 600，不入库不移库；由用户从本机 `D:\Temp\yuketang_cookie.txt` scp 上去）
- SMTP：复用 4B 已有 `SMTP_USER/SMTP_PASS/SMTP_TO`（systemd env.conf，exam-watch.service 挂同一 EnvironmentFile）；SMTP_TO 若未配则默认发给 SMTP_USER 自身（send_email.py 现成行为）

## 数据流与错误处理

1. 到点 → service 执行 → cookie 失效（401）→ 告警一次并停止（邮件 + alert 文件）
2. 网络抖动 → 不告警，state.last_error 记录，下轮恢复
3. 考试发现（use_count 或 leaf_type=5 >0）→ alert 文件 + QQ 邮件 → 停止轮询
4. **首轮基线（state 文件缺失）**：若首轮信号已 >0，直接判定发现并告警（用户监控起点是「现在没有」，部署时已有即用户最想知道的）；若为 0，记录基线后静默退出
5. 邮件失败（env.conf 缺失 / SMTP 5xx）→ 记 `state.mail_failed`，alert 文件照写（控制台提示仍生效），下一轮重试邮件；连续失败不刷屏（alert 文件已存在则不再追加）
6. exam_watch.py 崩溃 → systemd 记日志；timer 下轮再唤醒（oneshot 不常驻）

## 测试

- `broker/tests/test_exam_watch.py`：mock urllib 响应（use_count=0/1、leaf_type 列表、401、超时）→ 断言判定、状态文件、告警文件、邮件调用、退出码；首轮基线逻辑
- `console/tests/test_feed_exam.py`：alert json 解析、去重、merge 进 messages 结构
- 控制台侧回归：`python -m unittest discover` in `orchestra/console` 与 `orchestra/broker`
- 集成冒烟：4B 上手动跑一次 `python3 /home/liuxfs/broker/exam_watch.py`（真 cookie 真接口，当前应为「无考试，基线记录」）+ console `refresh` 后看 3100 无告警

## 不做（YAGNI）

- 不做考试放出前的倒计时/日历提醒（用户只问"什么时候放出来"）
- 不做考试入口点击/预约操作（只提醒）
- 不做 Windows 侧轮询（4B 为主；Windows 只是接收端）
- 不做 cookie 自动续期（雨课堂无公开刷新机制；过期告警后人工换）
