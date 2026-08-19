# T-nightly-radar-render
executor: shell
net: optional
result: T-{{DATE}}-nightly-radar-30-render
timeout: 1200
depends_on: T-{{DATE}}-nightly-radar-20-rank
mode: execute
detail: brief
required_outputs: digest.json, digest.txt, top5.json, validation.json
json_outputs: digest.json, top5.json, validation.json
validation_output: validation.json
validator: radar-render
---
env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 \
  /home/liuxfs/broker/radar_render.py \
  --input-root "{{RESULTS_ROOT}}/T-{{DATE}}-nightly-radar-20-rank" \
  --output-dir . \
  --date "{{DATE}}"
