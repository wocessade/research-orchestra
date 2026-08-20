# Cron Setup Guide

## Creating a Daily Push with Claude Code CronCreate

Use Claude Code's built-in `CronCreate` tool:

```
CronCreate:
  cron: "30 8 * * *"       # 08:30 Beijing time daily
  prompt: "Run the daily literature pipeline: search arXiv for papers matching [keywords], score top 30, deliver top 5 to email, archive to Zotero and Obsidian."
  recurring: true
  durable: true             # Survives session restarts
```

### Verify

After creation, immediately verify:
1. `cron list` shows the job
2. Manually trigger once to confirm end-to-end: search → score → email → Zotero → Obsidian
3. Check email arrives
4. Check Zotero has new entries
5. Check Obsidian has new notes

### Lessons from Past Failures

The original nature-skills pipeline failed because Hermes cron was a local/profile scheduler — jobs were lost on restart. Claude Code's `CronCreate` with `durable: true` persists to `.claude/scheduled_tasks.json` and survives restarts.

### Manual Fallback

If the cron doesn't fire:
1. Don't spend time debugging — just run manually: "跑一次文献推送"
2. Check `cron list` to confirm the job still exists
3. Verify email/Zotero/Obsidian chains independently

### 7-Day Auto-Expiry

Recurring tasks auto-expire after 7 days. Set a reminder to re-create or confirm renewal before expiry.
