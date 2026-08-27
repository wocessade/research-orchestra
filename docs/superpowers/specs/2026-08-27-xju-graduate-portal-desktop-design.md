# 新大研究生办事大厅 — 个人转接桌面（设计）

日期：2026-08-27  
状态：架构已批准；执行由 CC 主会话统筹 + haiku 子代理（DeepSeek prompt 包降级为备用路由）  
身份：研究生（非本科）  
门户：https://rhmh.xju.edu.cn/index.html#/ （金智 wisedu「网上办事服务大厅」，`Server: wisedu`，`X-Frame-Options: SAMEORIGIN`）

## 1. 目标

官方大厅约近百个入口，本科/研究生混排，有用信息密度低。本方案不改学校系统，只做**个人转接**：

1. 用 owner **已登录**的本机浏览器会话，把门户服务目录摸清。
2. 每个入口只探到「落地页 / 无权限 / 跳到独立子系统」。
3. 筛出研究生实际能用的入口。
4. 做一个极简个人前端桌面：分类磁贴 + 搜索 + 跳转官方页。

成功标准（v1）：打开桌面能在 10 秒内找到报到/培养/成绩/一卡通等研究生常用入口；桌面不含本科专用项；仓库与聊天中**零账密、零 cookie 文件**。

## 2. 非目标

- 不递归爬教务 / 财务 / 宿舍等独立子系统的每一页、每一个 XHR。
- 登录代填仅限：owner 主动提供凭据后由协调者瞬时代填一次；不写入任何文件、不进 explorer/sentry 上下文；不绕过验证码、不破解 SSO。
- **不做任何新闻/通知聚合**（owner 强调）：首页通知公告与新闻资讯栏目不抓取；服务目录（`#/servicelist`、`#/list`）中的新闻/资讯/通知类入口一律标 `junk_reason: news`，不展开；官网（www.xju.edu.cn 等）新闻外链不点开、不收录；桌面没有任何新闻/公告/通知流。
- 不 iframe 嵌官方页（同源策略禁止）。
- 不把账号密码写入仓库、环境变量文件、prompt 正文、聊天记录（凭据只允许出现在 owner→协调者的瞬态对话中）。
- 不 push 摸站原始 HAR / cookie / 带 token 的 URL。

## 3. 深度边界（硬）

| 层 | 做什么 | 停 |
|----|--------|----|
| L0 门户壳 | 记下首页 URL、登录态是否有效、目录接口 | — |
| L1 服务目录 | 从 `https://rhmh.xju.edu.cn/default/index.html#/servicelist` 与 `#/list` 两页（各自大几十条）拉入口并集，按 service_id/URL 去重（名称、分类、目标 URL、可见身份若有） | 列表并集拿全即停 |
| L2 落地 | 用已登录会话打开该入口 **一次**；记录 HTTP/落地标题/是否无权限/是否跳转外域 | 一跳之后停 |
| L3 子系统 | 仅当 L2 跳到不同 host：记录 `host` + `reachable_with_sso` | **禁止**再点子系统内菜单 |

「整个网站」= **L0–L2 覆盖门户目录全部入口**，不是新疆大学全部信息化系统。

## 4. 架构

```
Owner 本机 Chrome（远程调试 9222）
        │  登录态：owner 引导登录，或凭据由 owner 瞬态提供由协调者代填
        ▼
协调者（CC 主会话）
        │  拉 L1（servicelist+list 并集）→ 切块 → 写 INDEX → 写 probe.cjs
        ├─ explorer-A (haiku)  只调 probe.cjs，追加 shards/A.md
        ├─ explorer-B (haiku)  只调 probe.cjs，追加 shards/B.md
        ├─ explorer-C (haiku)  只调 probe.cjs，追加 shards/C.md
        └─ sentry（CC 主会话）  只读分片 → 合并 TOPOLOGY.md + USABLE.md + REJECT.md
                │
                ▼
个人桌面（静态页，haiku 生成 + CC 检查）  只消费 USABLE.md
```

数据流：目录 JSON/表格 → 分片记录 → 筛选表 → 桌面配置（无密钥）。

## 5. 工作区（落盘位置）

临时摸站产物一律 **`D:\Temp\xju-portal-map\`**（不进 git）。桌面源码若要进仓库，另放 `xju-desktop/`，且不得拷贝 cookie/HAR。

```
D:\Temp\xju-portal-map\
  INDEX.md              # 目录全表 + 分片分配（协调者独占写）
  TOPOLOGY.md           # 站点图：门户 → 入口 → host
  USABLE.md             # 研究生可用清单（桌面唯一数据源）
  REJECT.md             # 本科/无权限/空壳/死链/新闻
  shards/
    A.md
    B.md
    C.md
  tools/
    probe.cjs           # 通用探测脚本：URL→JSON（haiku 只调用它）
  raw/                  # 可选：目录 API 响应（去 cookie、去 token 查询串）
```

公共 md 约定：协调者与 sentry 可以改 `INDEX.md` / `TOPOLOGY.md` / `USABLE.md` / `REJECT.md`。Explorer **只追加自己的 shard**，禁止改别人的文件、禁止改 INDEX 的分配表以外的行。

## 6. 分片记录格式（每入口一行块）

```markdown
## {service_id}
- name: 
- catalog_group: 
- target_url:          # 去 token/jsessionid
- identity_hint:       # 目录里若写了适用身份
- http_or_result:      # 200 | 302→host | 403 | 登录墙 | 超时 | 空页
- landing_title: 
- sso_hop_host:        # 无则 empty
- graduate_relevant:   yes | no | unknown
- usable:              yes | no
- junk_reason:         # 新闻 / 本科专用 / 无权限 / 空壳 / 重复 / 教师 / 死链 / 其它
- notes:               # ≤2 句
```

`usable=yes` 当且仅当：研究生身份能打开落地页或完成 SSO 进入子系统首页，**且**名称/页面表明与培养、学籍、成绩、选课、住宿、校园卡、缴费、图书馆、研究生院办事等相关。教师、本科招生、无关展示页一律 `no`。

## 7. 多 agent 分工

| 角色 | 模型侧 | 职责 | 文件 |
|------|--------|------|------|
| 协调者 | CC 主会话 | 登录态确认（必要时凭据代填）；导出 L1 并集；均分入口；维护 INDEX；写 probe.cjs；sentry 汇总；桌面检查 | INDEX.md、TOPOLOGY/USABLE/REJECT、xju-desktop/ |
| explorer×3 | haiku 子代理（纯机械） | 只读 INDEX 分配行 → `node tools/probe.cjs` → 按模板追加分片块 + 进度注释；禁止判断 usable、禁止改他人文件 | 各自 shards/*.md |
| sentry | CC 主会话 | 覆盖核对、去重、本硕过滤、新闻剔除、写 TOPOLOGY/USABLE/REJECT、抽检 ≥10 条 | 那三份 + REJECT |
| 桌面 | haiku 生成，CC 检查 | 把 USABLE.md 编成 sites.json + 单页 index.html（搜索+分组磁贴+window.open） | xju-desktop/ |

并行上限 3 个 explorer（同一浏览器 profile 上过多标签会踢登录）。同文件不双写。叶子不 commit。凭据只存在于协调者会话内存，不进任何子代理上下文。

## 8. 登录与安全

- 路径 A（默认）：Owner 操作：Chrome 启动远程调试 → 手动打开门户 → **自己**输入账密（含验证码）→ 进入首页后再让 agent 接 CDP。
- 路径 B（owner 主动授权，已采用）：owner 把本校账号凭据发给协调者，由协调者连接 CDP 后用 `page.fill` 代填一次；遇验证码仍请 owner 在浏览器窗口内手动完成；凭据仅存协调者会话内存，不写文件、不进 explorer/sentry 的 prompt 与上下文、不进仓库与聊天记录副本；任务完成后 owner 应改密。
- Agent 禁止：索要或回显密码；把 `document.cookie` 写入磁盘；提交 HAR 到仓库。
- 会话失效：停手，请 owner 重新登录，再从 INDEX 未完成行继续。

建议启动（owner 本机，路径按本机 Chrome 调整）：

```text
chrome.exe --remote-debugging-port=9222 --user-data-dir=D:\Temp\chrome-xju-debug
```

## 9. 个人桌面 v1

单页静态：本地打开即可（或任意静态服务器）。

- 数据：构建时把 `USABLE.md` 编成 `sites.json`（仅 name、group、url、notes）。
- UI：顶栏搜索；分组（培养 / 学籍成绩 / 生活卡务 / 办事 / 其它）；磁贴点击 `window.open` 官方 URL。
- 不做：代理官方 API、代登录、嵌 iframe、同步通知数字。

学校改版后：重跑 L1+L2 筛一遍，重生 `sites.json`，不手改几十个链接。

## 10. 验收

- INDEX 中每个目录入口都有且仅有一个 shard 块。
- USABLE 无本科专用、无死链（抽检 ≥10 条可点开）。
- 桌面只渲染 USABLE；仓库无账密、无 cookie 文件。
- TOPOLOGY 能看出门户与外跳 host 列表。

## 11. 配套文件

DeepSeek 可粘贴 prompt：`docs/superpowers/plans/2026-08-27-xju-portal-deepseek-prompts.md`
