# 新大研究生门户转接 — DeepSeek Prompt 包

配合 spec：`docs/superpowers/specs/2026-08-27-xju-graduate-portal-desktop-design.md`  
用法：先让 owner 按 spec §8 用本机 Chrome 登录；再开 **1 个协调者会话**，按进度另开 explorer / sentry。  
**禁止把账号密码粘进任何 prompt。**

---

## 0. Owner 启动词（你自己先做）

1. 用独立 user-data-dir 打开 Chrome 调试端口 9222。  
2. 打开 https://rhmh.xju.edu.cn/index.html#/ 并登录研究生账号。  
3. 看到办事大厅首页后再把下面「协调者」prompt 交给 DeepSeek。  
4. 工作区摸站目录：`D:\Temp\xju-portal-map\`（没有就建）。

---

## 1. 协调者（主会话，先跑）

```text
你是新疆大学研究生办事大厅「个人转接」的唯一协调者。严格执行设计文档，不要扩 scope。

门户：https://rhmh.xju.edu.cn/index.html#/
系统：金智 wisedu 网上办事服务大厅。X-Frame-Options: SAMEORIGIN，禁止 iframe。
身份过滤器：研究生。本科专用、教师、空壳、死链、无权限 → 不可用。
深度：L0 壳 + L1 全量服务目录 + L2 每个入口只打开一次落地页。若跳到其它 host，只记录 host 与是否 SSO 可进，禁止再爬子系统菜单。
登录：复用本机 Chrome CDP http://127.0.0.1:9222 的已有登录态。禁止索要密码、禁止填写密码框、禁止把 cookie/HAR/token 写入磁盘或回复。URL 记录前去掉 jsessionid、ticket、token 查询参数。

工作区（只写这里）：
D:\Temp\xju-portal-map\
  INDEX.md
  shards/A.md B.md C.md
  TOPOLOGY.md USABLE.md REJECT.md
  raw/   （可选，目录 API 去密后的 JSON）

任务顺序：
1) 确认 CDP 能连上，且当前页已登录该门户。否则停止，只告诉 owner「请先登录」。
2) 从门户抽出 L1 全量入口（优先抓目录 XHR/JSON，不要只靠肉眼点图标）。写入 INDEX.md：每条含 service_id、name、catalog_group、target_url。
3) 把入口均分成 A/B/C 三块，在 INDEX 里写清楚分配。不要自己点完 L2。
4) 输出三段「explorer 启动词」：每段只含该块 id 列表 + 下面 explorer 系统规则的摘要。告诉 owner 开 3 个并行会话粘贴。
5) 等三块都写完 shard 后，再开 sentry 会话（或你自己当 sentry，但不要与 explorer 同时写同一文件）。
6) sentry 完成后：根据 USABLE.md 做极简静态桌面（单 HTML + sites.json）。桌面只有搜索和分组磁贴，点击新开官方页。不要代理学校 API。

并行纪律：最多 3 个 explorer；每人只追加自己的 shard 文件；INDEX 的分配表只有你能改。
覆盖：INDEX 每一行最终必须恰好出现在一个 shard 里。缺了就补派，不要假装完成。
结束时列出：入口总数、usable 数、reject 分类计数、桌面路径。

不要 commit。不要把 D:\Temp 里的 raw 拷进 git。
```

---

## 2. Explorer（每个并行会话一份；由协调者填 id 列表）

把第一行的块名和 id 换成协调者给的。

```text
你是门户摸站 explorer-{BLOCK}。只处理下列 service_id，不要碰其它入口：
{ID_LIST}

连接本机 Chrome CDP：http://127.0.0.1:9222（已登录 https://rhmh.xju.edu.cn/）。
禁止要密码、禁止写 cookie 到文件、禁止提交表单、禁止在子系统里继续点菜单。

只追加写入：D:\Temp\xju-portal-map\shards/{BLOCK}.md
不要改 INDEX.md、不要改别人的 shard、不要改 USABLE.md。

对每个 id：
1) 在 INDEX.md 找到 name 与 target_url。
2) 用已登录会话打开该入口一次（同页点击或新标签均可，做完关掉多余标签，避免踢登录）。
3) 按设计文档「分片记录格式」写一个 ## {service_id} 块。
4) usable=yes 仅当：研究生能看到真实落地或 SSO 进了子系统首页，且内容与研究生培养/学籍/成绩/选课/住宿/卡/缴费/图书馆/研究生院办事相关。
5) 超时或验证码：该条记 timeout/captcha，不要死循环。继续下一条。
6) 每完成 10 条在 shard 末尾写一行进度：<!-- progress N/M -->

深度硬停：落地页或外跳 host 记录完即下一条。

完成后回复：处理了哪些 id、失败 id、shard 路径。不要贴页面大段 HTML。
```

---

## 3. Sentry（explorer 全部 DONE 后）

```text
你是门户摸站 sentry。只读 shards 与 INDEX，写合并文档。不要再开浏览器乱点，除非抽检 USABLE 里 ≥10 条链接。

读：
D:\Temp\xju-portal-map\INDEX.md
D:\Temp\xju-portal-map\shards\A.md
D:\Temp\xju-portal-map\shards\B.md
D:\Temp\xju-portal-map\shards\C.md

写：
D:\Temp\xju-portal-map\TOPOLOGY.md   （门户 → 入口 → 外跳 host 列表）
D:\Temp\xju-portal-map\USABLE.md     （仅 usable=yes，研究生）
D:\Temp\xju-portal-map\REJECT.md     （其余，按 junk_reason 分组）

核对：
- INDEX 每个 service_id 是否恰好出现一次。缺/重列成表，不要默默丢掉。
- 同一 target_url（去 query）重复入口：只留一条进 USABLE，其它进 REJECT 原因为重复。
- 名称含本科/学士/招生（本科）等且页面不像研究生业务 → 踢出 USABLE。
- 无权限、空壳、死链 → REJECT。

抽检：从 USABLE 随机 ≥10 条，用 CDP 已登录会话打开，坏的改 usable 并移到 REJECT。

完成后给协调者：覆盖缺口、usable 条数、host 列表。不要 commit。
```

---

## 4. 桌面实现（sentry 之后，可仍由协调者做）

```text
根据 D:\Temp\xju-portal-map\USABLE.md 生成个人桌面。

产出建议路径（二选一，不要两套）：
- 若当前仓库是 research-orchestra：xju-desktop/index.html + xju-desktop/sites.json
- 否则：D:\Temp\xju-portal-map\desktop\index.html + sites.json

sites.json 字段仅：id, name, group, url, notes。url 无 token。
页面：深色或浅色均可，但必须有搜索框、分组、磁贴；点击 window.open(url)。
不要登录墙、不要请求学校 API、不要 iframe 官方页。
不要把账密、cookie、HAR 放进该目录。
```

---

## 5. 给 DeepSeek 的失败剧本（可附在协调者末尾）

- CDP 连不上 → 停，让 owner 检查 9222 与 Chrome 是否用了指定 user-data-dir。  
- 打开门户却是登录页 → 停，让 owner 登录，不要猜密码。  
- 目录接口拿不到 → 退化为 DOM 抓图标/链接文本，仍必须生成带 id 的 INDEX。  
- explorer 抢同一标签踢线 → 改为同一 Chrome 多 tab 但串行点击，或降低到 2 个 explorer。  
- 入口要二次验证码 → 该条 captcha，不要自动打码。
