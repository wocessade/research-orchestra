#!/usr/bin/env bash
# 每晚注入四阶段文献雷达任务；先预检并 staging，发布期间 marker 阻止 Broker 读取半成品。
set -euo pipefail

D="${ORCHESTRA_DATE:-$(date +%Y%m%d)}"
TASKS_DIR="${ORCHESTRA_TASKS_DIR:-/mnt/broker/tasks}"
RESULTS_DIR="${ORCHESTRA_RESULTS_DIR:-/mnt/broker/results}"
TEMPLATES_DIR="${ORCHESTRA_TEMPLATES_DIR:-/home/liuxfs/broker/templates}"
PROC_ROOT="${ORCHESTRA_PROC_ROOT:-/proc}"
STAGES=(10-fetch 20-rank 30-render 40-notify)

mkdir -p "$TASKS_DIR"
for stage in "${STAGES[@]}"; do
  template="$TEMPLATES_DIR/nightly-radar-${stage#*-}.md"
  [ -f "$template" ] || {
    echo "missing template: $template" >&2
    exit 1
  }
done

marker="$TASKS_DIR/.radar-inject-$D"
staging="$TASKS_DIR/.radar-stage-$D.$$"
boot_id="$(cat "$PROC_ROOT/sys/kernel/random/boot_id" 2>/dev/null || printf 'unknown')"

process_starttime() {
  local stat_file stat_line stat_tail value
  local -a stat_fields
  stat_file="$PROC_ROOT/$1/stat"
  [ -r "$stat_file" ] || return 1
  stat_line="$(cat "$stat_file" 2>/dev/null)" || return 1
  # /proc/<pid>/stat 的 comm 字段可含空格或右括号；从最后一个 ")" 后按字段取第 22 项。
  stat_tail="${stat_line##*)}"
  stat_tail="${stat_tail# }"
  read -r -a stat_fields <<< "$stat_tail"
  [ "${#stat_fields[@]}" -ge 20 ] || return 1
  value="${stat_fields[19]}"
  case "$value" in
    ''|*[!0-9]*) return 1 ;;
  esac
  printf '%s\n' "$value"
}

starttime="$(process_starttime "$$" || printf 'unknown')"
owner="$(hostname):${boot_id}:$$:${starttime}"

acquire_marker() {
  owner_missing_retries=0
  while ! mkdir "$marker" 2>/dev/null; do
    old_owner="$(cat "$marker/owner" 2>/dev/null || true)"
    if [ -z "$old_owner" ] && [ "$owner_missing_retries" -lt 20 ]; then
      owner_missing_retries=$((owner_missing_retries + 1))
      sleep 0.05
      continue
    fi
    owner_missing_retries=0
    old_host="${old_owner%%:*}"
    rest="${old_owner#*:}"
    old_boot="${rest%%:*}"
    rest="${rest#*:}"
    old_pid="${rest%%:*}"
    if [ "$rest" = "$old_pid" ]; then
      old_starttime="unknown"
    else
      old_starttime="${rest#*:}"
    fi
    case "$old_pid" in
      ''|0|*[!0-9]*)
        pid_is_valid=false
        current_starttime="unknown"
        ;;
      *)
        pid_is_valid=true
        current_starttime="$(process_starttime "$old_pid" || printf 'unknown')"
        ;;
    esac
    if [ "$old_host" = "$(hostname)" ] &&
       [ "$old_boot" = "$boot_id" ] &&
       [ "$pid_is_valid" = true ] &&
       kill -0 "$old_pid" 2>/dev/null &&
       { [ "$old_starttime" = "unknown" ] ||
         [ "$current_starttime" = "unknown" ] ||
         [ "$old_starttime" = "$current_starttime" ]; }; then
      echo "radar injection already running for $D (owner $old_owner)" >&2
      exit 0
    fi
    stale="$TASKS_DIR/.radar-inject-stale-$D.$$"
    if mv "$marker" "$stale" 2>/dev/null; then
      rm -rf "$stale"
    fi
  done
  printf '%s\n' "$owner" > "$marker/owner"
}

acquire_marker
mkdir "$staging"
cleanup() {
  rm -rf "$staging"
  if [ "$(cat "$marker/owner" 2>/dev/null || true)" = "$owner" ]; then
    rm -rf "$marker"
  fi
}
trap cleanup EXIT INT TERM

injected=0
for stage in "${STAGES[@]}"; do
  template="$TEMPLATES_DIR/nightly-radar-${stage#*-}.md"
  task="$TASKS_DIR/T-${D}-nightly-radar-${stage}.md"
  [ -f "$task" ] && continue
  tmp="$staging/${task##*/}"
  sed \
    -e "s/{{DATE}}/${D}/g" \
    -e "s|{{RESULTS_ROOT}}|${RESULTS_DIR}|g" \
    "$template" > "$tmp"
  [ -s "$tmp" ] || {
    echo "rendered task is empty: $tmp" >&2
    exit 1
  }
  injected=$((injected + 1))
done

for tmp in "$staging"/*.md; do
  [ -e "$tmp" ] || break
  task="$TASKS_DIR/${tmp##*/}"
  mv "$tmp" "$task"
  echo "injected $task"
done

cleanup
trap - EXIT INT TERM

echo "nightly radar injection complete: ${injected} new task(s)"
