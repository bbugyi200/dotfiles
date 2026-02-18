#!/usr/bin/env bash
set -euo pipefail

# Read JSON from stdin
input=$(cat)

# --- Extract fields from JSON ---
session_id=$(echo "$input" | jq -r '.session_id // ""')
cwd=$(echo "$input" | jq -r '.cwd // ""')
model_name=$(echo "$input" | jq -r '.model.display_name // ""')

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


# --- ANSI color codes ---
DIM='\033[2m'
BOLD='\033[1m'
BOLD_CYAN='\033[1;36m'
BOLD_BLUE='\033[1;34m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
MAGENTA='\033[35m'
RESET='\033[0m'

# --- Build output ---
sep="${DIM}  |  ${RESET}"
colored_model=""
if [[ -n "$model_name" ]]; then
  colored_model="${BOLD_CYAN}[${model_name}]${RESET}  "
fi
# CWD: dim prefix + bold blue basename
cwd_dir=$(dirname "$short_cwd")
cwd_base=$(basename "$short_cwd")
if [[ "$short_cwd" == "~" || "$short_cwd" == "/" ]]; then
  colored_cwd="${BOLD_BLUE}${short_cwd}${RESET}"
elif [[ "$cwd_dir" == "." ]]; then
  colored_cwd="${BOLD_BLUE}${cwd_base}${RESET}"
elif [[ "$cwd_dir" == "/" ]]; then
  colored_cwd="${DIM}/${RESET}${BOLD_BLUE}${cwd_base}${RESET}"
else
  colored_cwd="${DIM}${cwd_dir}/${RESET}${BOLD_BLUE}${cwd_base}${RESET}"
fi
# --- Git info ---
git_info=""
if git -C "$cwd" rev-parse --is-inside-work-tree &>/dev/null; then
  branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [[ -n "$branch" ]]; then
    git_info="${MAGENTA}${branch}${RESET}"

    # Dirty indicator
    if [[ -n $(git -C "$cwd" status --porcelain 2>/dev/null) ]]; then
      git_info+="${YELLOW}*${RESET}"
    fi

    # Ahead/behind upstream
    ahead=$(git -C "$cwd" rev-list --count '@{u}..HEAD' 2>/dev/null || echo "")
    behind=$(git -C "$cwd" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo "")
    if [[ -n "$ahead" && "$ahead" -gt 0 ]]; then
      git_info+="${GREEN}↑${ahead}${RESET}"
    fi
    if [[ -n "$behind" && "$behind" -gt 0 ]]; then
      git_info+="${RED}↓${behind}${RESET}"
    fi
  fi
fi

# Build git section with surrounding separators
git_section=""
if [[ -n "$git_info" ]]; then
  git_section="${sep}${git_info}"
fi

if [[ -n "$session_name" ]]; then
  echo -e "${DIM}${session_name}${RESET}${sep}${colored_model}${colored_cwd}${git_section}"
else
  echo -e "${colored_model}${colored_cwd}${git_section}"
fi
