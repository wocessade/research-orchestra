# T-20260819-ctl-single
executor: shell
net: required
result: T-20260819-ctl-single
timeout: 600
---
cd /mnt/broker/demo && mkdir -p /mnt/broker/results/T-20260819-ctl-single && python3 extract_single.py --text material/extract_text.txt --gold material/gold.json --out result_ctl.json && python3 score.py --gold material/gold.json --result result_ctl.json --exp-id EXP-001 --out /mnt/broker/results/T-20260819-ctl-single/metrics.json
