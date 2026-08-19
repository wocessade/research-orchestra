# 夜间雷达日报 → Zotero 直连（想法记录，2026-08-20）

> 状态：**方向已提出，待用户拍板**。拍板后走 brainstorming 设计流程（细节问题见文末）。

## 痛点（用户原话）

"文献日报目前不太实用：手机上收到信息，去电脑上还得一个一个翻出来下载了看。"

即：现日报 = digest.txt 中文摘要邮件（标题/arXiv ID/总分/一句话理由），读全文需手动逐篇下载——手机到电脑的断层。

## 方向（用户提出）

把 Zotero 文献管理接入 Pi 侧自动化：

```
夜间雷达（4B）→ 六维评分选 top5 → 下载 PDF
    → zotero_push 脚本（Pi，stdlib）→ Zotero Web API（api.zotero.org）
    → 用户 Zotero 库（自动建收藏集「雷达日报/日期」+ 条目含摘要/六维分数标签/PDF 附件）
    → 手机（Zotero App/网页）与电脑客户端自动同步 → 点开即读，可笔记批注
邮件日报降级为"通知"：今日 5 篇已入库 + 摘要正文
```

## 已明确的约束与事实

- 用户 Zotero 侧：需在 zotero.org/settings/keys 申请 API key（写入权限）+ userID；key 走 Pi systemd env 注入（不入库）
- 免费附件空间 300MB：5 篇/天 ≈ 1-5MB，可用 2-3 个月；升级路径 = 4B NAS 跑 WebDAV 自建附件存储（元数据仍走 Zotero 云）
- 验收必须含：Pi → api.zotero.org 网络可达性真机实测 + 真机 push 测试
- 与双 agent 想法池中「雷达日报智能化（codex 总结+排序）」互补不冲突：Zotero 解决"读"的链路，智能化解决"筛"的质量

## 待用户回答的细节问题

1. 方向本身是否确认（Zotero 主链路）
2. 手机端习惯：Zotero App / 网页版 / 都行
3. 邮件日报：保留（降级为通知）还是取消
4. 下载策略：top5 全下 PDF，还是只下 top2-3（省附件空间）

## 关联

- 雷达管线验收：`.tasks/completed/023_nightly-radar-pipeline/`
- 雷达模板：`orchestra/templates/nightly-radar.md`
- 邮件投递：4B `/usr/local/bin/send_email.py`
