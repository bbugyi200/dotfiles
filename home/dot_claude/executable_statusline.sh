#!/usr/bin/env bash
set -euo pipefail

# Read JSON from stdin
input=$(cat)

# --- Extract fields from JSON ---
session_id=$(echo "$input" | jq -r '.session_id // ""')
cwd=$(echo "$input" | jq -r '.cwd // ""')
model_name=$(echo "$input" | jq -r '.model.display_name // ""')
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')

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

# --- Duration: convert ms to Xm Ys ---
total_secs=$(( ${duration_ms%.*} / 1000 ))
mins=$(( total_secs / 60 ))
secs=$(( total_secs % 60 ))
duration_str="⏱️ ${mins}m ${secs}s"

# --- Model: used in build output below ---

# --- ANSI color codes ---
DIM='\033[2m'
BOLD='\033[1m'
BOLD_CYAN='\033[1;36m'
GREEN='\033[32m'
RESET='\033[0m'

# --- Build output ---
sep="${DIM}  |  ${RESET}"
colored_model=""
if [[ -n "$model_name" ]]; then
  colored_model="${BOLD_CYAN}[${model_name}]${RESET}  "
fi
colored_cwd="${BOLD}${short_cwd}${RESET}"
colored_duration="${GREEN}${duration_str}${RESET}"

if [[ -n "$session_name" ]]; then
  echo -e "${DIM}${session_name}${RESET}${sep}${colored_model}${colored_cwd}${sep}${colored_duration}"
else
  echo -e "${colored_model}${colored_cwd}${sep}${colored_duration}"
fi
