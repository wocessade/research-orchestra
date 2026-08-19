# T-nightly-radar-notify
executor: shell
net: required
result: T-{{DATE}}-nightly-radar-40-notify
timeout: 300
depends_on: T-{{DATE}}-nightly-radar-30-render
mode: brief
detail: brief
required_outputs: notification.json
json_outputs: notification.json
---
env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 \
  /home/liuxfs/broker/radar_notify.py \
  --render-root "{{RESULTS_ROOT}}/T-{{DATE}}-nightly-radar-30-render" \
  --state-root "{{RESULTS_ROOT}}/notifications" \
  --output-dir . \
  --date "{{DATE}}"
