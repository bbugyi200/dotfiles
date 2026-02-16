#!/usr/bin/env bash
set -euo pipefail

# Read JSON from stdin
input=$(cat)

# --- Extract fields from JSON ---
session_id=$(echo "$input" | jq -r '.session_id // ""')
cwd=$(echo "$input" | jq -r '.cwd // ""')

# --- CWD: shorten to ~/relative ---
home="${HOME:-$(eval echo ~)}"
short_cwd="${cwd/#$home/\~}"

# --- Cache: /tmp/claude-statusline-cache-<session_id> ---
cache="/tmp/claude-statusline-cache-${session_id}"

if [[ -f "$cache" ]]; then
  session_name=$(< "$cache")
else
  # Session name: look up via `claude conversation list`
  session_name=""
  if command -v claude &>/dev/null && [[ -n "$session_id" ]]; then
    session_name=$(claude conversation list --json 2>/dev/null \
      | jq -r --arg sid "$session_id" \
        '.[] | select(.session_id == $sid) | .name // ""' 2>/dev/null || echo "")
  fi

  # Write cache
  printf '%s' "$session_name" > "$cache"
fi

# --- Build output ---
parts=()

if [[ -n "$session_name" ]]; then
  parts+=("$session_name")
fi

parts+=("$short_cwd")

# Join with " | "
IFS=' | '
echo "${parts[*]}"
