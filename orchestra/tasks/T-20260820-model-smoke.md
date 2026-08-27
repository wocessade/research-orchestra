# T-20260820-model-smoke
executor: dsh
net: required
result: T-20260820-model-smoke
timeout: 600
model: flash
---
你是模型冒烟任务。对以下 3 篇论文标题按六维打分（Topic 35/Method 20/Source 15/Network 10/Applied 10/Archival 10，总分 100，用 python3 核算 sum 一致），选出总分最高 1 篇，在工作目录写 digest.json（数组：title/arxiv_id/url/scores/total/rationale）与 digest.txt（中文：标题/总分/一句话理由）：
1) "Attention Is All You Need" 2) "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" 3) "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
