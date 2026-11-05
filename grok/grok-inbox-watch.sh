#!/usr/bin/env bash
# 省 token 的收件检测：每次只读一个值（日志行数），变了才唤醒 agent 读日志。
# 行数不变时静默退出，不产生任何 agent 调用。
# @GROK_DIR@ 由 deploy.sh 安装时替换为 grok/ 目录的实际路径。
set -euo pipefail
source "$HATCH_HOOK_RUNTIME"

LOG="@GROK_DIR@/grok-inbox.log"
STATE_DIR="$HOME/hooks/state/grok-inbox-watch"
STATE_FILE="$STATE_DIR/lines"
DRY_RUN="${HATCH_HOOK_DRY_RUN:-0}"

if [[ ! -f "$LOG" ]]; then
  silent "log-missing" '{"lines":0}'
fi

# 只读一个值：当前总行数
current="$(wc -l < "$LOG" | tr -d ' ')"

previous=""
if [[ -f "$STATE_FILE" ]]; then
  previous="$(tr -d ' \n' < "$STATE_FILE")"
fi
if ! [[ "$previous" =~ ^[0-9]+$ ]]; then
  previous=""
fi

# 第一次运行：以当前行数为基线，不唤醒（避免把历史全报一遍）
if [[ -z "$previous" ]]; then
  if [[ "$DRY_RUN" != "1" ]]; then
    mkdir -p "$STATE_DIR"
    printf '%s' "$current" > "$STATE_FILE"
  fi
  silent "baseline-initialized" "{\"lines\":$current}"
fi

# 值没变：静默，不读日志
if [[ "$current" -eq "$previous" ]]; then
  silent "no-change" "{\"lines\":$current}"
fi

# 值变了：记下新行数，唤醒 worker 去读新增的行并通知用户
if [[ "$DRY_RUN" != "1" ]]; then
  mkdir -p "$STATE_DIR"
  printf '%s' "$current" > "$STATE_FILE"
fi
wake "inbox-changed" "{\"previous\":$previous,\"current\":$current}"
