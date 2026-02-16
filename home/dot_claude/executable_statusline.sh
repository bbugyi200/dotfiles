#!/usr/bin/env bash
set -euo pipefail

# Read JSON from stdin
input=$(cat)

# --- Extract fields from JSON ---
session_id=$(echo "$input" | jq -r '.session_id // ""')
cwd=$(echo "$input" | jq -r '.cwd // ""')
transcript=$(echo "$input" | jq -r '.transcript_path // ""')

# --- CWD: shorten to ~/relative ---
home="${HOME:-$(eval echo ~)}"
short_cwd="${cwd/#$home/\~}"

# --- Cache: /tmp/claude-statusline-cache-<session_id> ---
cache="/tmp/claude-statusline-cache-${session_id}"

if [[ -f "$cache" ]]; then
  session_name=$(sed -n '1p' "$cache")
  first_prompt=$(sed -n '2p' "$cache")
else
  # Session name: look up via `claude conversation list`
  session_name=""
  if command -v claude &>/dev/null && [[ -n "$session_id" ]]; then
    session_name=$(claude conversation list --json 2>/dev/null \
      | jq -r --arg sid "$session_id" \
        '.[] | select(.session_id == $sid) | .name // ""' 2>/dev/null || echo "")
  fi

  # Initial prompt: parse transcript JSONL for first real user message
  first_prompt=""
  if [[ -n "$transcript" && -f "$transcript" ]]; then
    first_prompt=$(jq -r '
      select(.type == "user" and .userType == "external")
      | .message.content
      | if type == "string" then . else empty end
    ' "$transcript" 2>/dev/null \
      | grep -v '^$' \
      | grep -v '^[[:space:]]*$' \
      | grep -v '^[[:space:]]*<' \
      | grep -v '^Caveat:' \
      | head -1 \
      | sed 's/^[[:space:]]*//' \
      | sed 's/^ultrathink: *//' \
      | cut -c1-60)
    [[ ${#first_prompt} -ge 60 ]] && first_prompt="${first_prompt}..."
  fi

  # Write cache
  printf '%s\n%s\n' "$session_name" "$first_prompt" > "$cache"
fi

# --- Build output ---
parts=()

if [[ -n "$session_name" ]]; then
  parts+=("$session_name")
fi

parts+=("$short_cwd")

if [[ -n "$first_prompt" ]]; then
  parts+=("\"${first_prompt}\"")
fi

# Join with " | "
IFS=' | '
echo "${parts[*]}"
