# T-20260819-radar-dryrun
executor: dsh
net: required
result: T-20260819-nightly-radar
---
你是每日文献雷达。完成以下任务，全部产出写入工作目录：

## 1. 抓取
用 arXiv API 抓取最近 24 小时提交的论文（cs.CL 与 cs.LG 各取最新 30 篇，用 export.arxiv.org 的 api/query 接口）。

## 2. 六维评分（30 篇粗筛出 5 篇）
对每篇论文按六维打分（总分 100）：
1. Topic Match (max 35)：与"大模型/Agent/多模态/信息抽取/舆情分析"的相关度；低于 10 分直接淘汰
2. Methodological Value (max 20)：模型设计、训练方法、评估质量
3. Source Quality (max 15)：会议/期刊档次、引用、可信度
4. Network Relevance (max 10)：知名实验室/作者、热门研究网络
5. Applied Value (max 10)：是否开源代码/基准/数据集
6. Archival Value (max 10)：综述潜质、基础性、长期参考价值
注意：每维不超过其上限；总分必须等于六维之和（重新核算，不要心算）。

## 3. 产出
在工作目录写两个文件：
- digest.json：JSON 数组，每项 {title, arxiv_id, url, scores:{topic,method,source,network,applied,archival}, total, rationale}
- digest.txt：人类可读中文摘要（每篇：标题 / arXiv ID / 总分 / 一句话理由）

## 4. 邮件投递
运行：python3 /usr/local/bin/send_email.py "文献日报 20260819" digest.txt
（send_email.py 已安装在系统路径；发送成功会输出 "email sent"）

## 5. 报告
最后报告：今日抓取数量、入选 5 篇的标题与总分、邮件是否发送成功。
