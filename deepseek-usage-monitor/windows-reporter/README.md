# windows-reporter（已停用）

Claude Code hooks 已从用户 `~/.claude/settings.json` 移除，本目录不再被默认调用。

- 保留脚本便于手动调试或日后恢复 hooks
- 恢复方式：将 `C:\Users\19041\.claude\settings.json.bak-hooks` 中的 `hooks` 段合并回 `settings.json`（若该备份仍在）
- 若恢复 hooks，脚本路径应为：`D:/pythonProject/deepseek-usage-monitor/windows-reporter/reporter.py`（已随仓库归拢变更）
