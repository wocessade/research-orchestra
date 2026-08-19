# T-nightly-radar
executor: dsh
net: required
result: T-{{DATE}}-nightly-radar
---
你是每日文献雷达。完成以下任务，全部产出写入工作目录：

## 1. 抓取
用 arXiv API 抓取最近 24 小时提交的论文：cat:cs.CL 与 cat:cs.LG 各取最新 30 篇
（export.arxiv.org 的 api/query 接口，max_results=30，sortBy=submittedDate，sortOrder=descending）。
按 arXiv ID 去重：跨类重复或同 ID 只保留一次，形成候选池（约 57–60 篇）。

## 2. 六维评分
对候选池**全部论文**逐一按六维打分（总分 100）：
1. Topic Match (max 35)：与"大模型/Agent/多模态/信息抽取/舆情分析"的相关度；低于 10 分直接淘汰
2. Methodological Value (max 20)：模型设计、训练方法、评估质量
3. Source Quality (max 15)：会议/期刊档次、引用、可信度
4. Network Relevance (max 10)：知名实验室/作者、热门研究网络
5. Applied Value (max 10)：是否开源代码/基准/数据集
6. Archival Value (max 10)：综述潜质、基础性、长期参考价值
注意：每维不超过其上限；总分 = 六维之和（写 digest.json 前用 python3 脚本核算 sum 与各维一致，禁止心算）。
最终选出总分最高的 5 篇；宁缺毋滥：通过 Topic 门槛的不足 5 篇就按实际数量输出。

## 3. 产出
在工作目录写四个文件：
- digest.json：JSON 数组，每项 {title, arxiv_id, url, scores:{topic,method,source,network,applied,archival}, total, rationale}
- digest.txt：人类可读中文摘要（每篇：标题 / arXiv ID / 总分 / 一句话理由）
- top5.json：入选论文的 digest.json 子集（便于下游 ingest 直接消费）
- papers_all.json：去重后全部候选论文的元数据（标题 / arXiv ID / 分类 / 提交时间）

## 4. 邮件投递（幂等，防止重试重复发信）
先检查标记文件 /tmp/radar-sent-{{DATE}} 是否存在：已存在则跳过本步（打印 "email already sent, skip"）。
运行：python3 /usr/local/bin/send_email.py "文献日报 {{DATE}}" digest.txt
（send_email.py 已安装在系统路径；发送成功会输出 "email sent"）
发送成功后创建标记文件 /tmp/radar-sent-{{DATE}}（内容一行 "sent"）。

## 5. 报告
最后报告：今日抓取数量、去重后候选数量、入选论文标题与总分、邮件是否发送成功（或已跳过）。
