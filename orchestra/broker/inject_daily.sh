#!/usr/bin/env bash
# 示例：每晚注入 arXiv 抓取任务（required 任务断网时 Broker 会自动跳过排队）
set -euo pipefail
D="$(date +%Y%m%d)"
TASK="/mnt/broker/tasks/T-${D}-nightly-arxiv.md"
[ -f "$TASK" ] && exit 0
cat > "$TASK" << 'EOF'
# T-nightly-arxiv
executor: shell
net: required
result: T-nightly-arxiv
---
curl -s "https://export.arxiv.org/api/query?search_query=cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=10" -o arxiv.xml && echo done
EOF
echo "injected $TASK"
