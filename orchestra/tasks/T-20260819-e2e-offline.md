# T-20260819-e2e-offline
executor: shell
net: optional
result: T-20260819-e2e-offline
---
for i in 1 2 3 4 5; do date +%s >> heartbeat.txt; sleep 240; done; echo offline-done
