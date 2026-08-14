#!/bin/bash

#################################################################################
# Regression tests for the `tmux_ai_window` AI-agent launcher.                  #
#                                                                               #
# tmux and provider binaries are stubbed so the launcher command strings and    #
# display-menu wiring can be inspected without opening real tmux windows or     #
# starting agent CLIs.                                                          #
#################################################################################

TMUX_AI_WINDOW_SCRIPT="${PWD}/home/bin/executable_tmux_ai_window"
PROVIDERS=(claude codex agy qwen opencode grok muse)
# Expected on-screen row order: providers sorted by their menu key
# (a=agy, c=claude, g=grok, m=muse, o=opencode, q=qwen, x=codex).
MENU_ORDER=(agy claude grok muse opencode qwen codex)
SYSTEM_PATH="/usr/bin:/bin"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TMUX_CALLS_FILE="${TEST_TMP}/tmux-calls.txt"
  TMUX_FAKE_PANE_DIR="${TEST_TMP}/pane dir"

  mkdir -p "${FAKE_BIN}" "${TMUX_FAKE_PANE_DIR}"

  cat >"${FAKE_BIN}/tmux" <<'EOF'
#!/bin/bash
{
  printf 'CALL:%s\n' "$1"
  for arg in "$@"; do
    printf 'ARG:%s\n' "$arg"
  done
  printf 'END\n'
} >>"${TMUX_CALLS_FILE}"

case "$1" in
display-message)
  if [[ "$2" == "-p" ]]; then
    printf '%s\n' "${TMUX_FAKE_PANE_DIR}"
  fi
  ;;
list-windows | run-shell | new-window | display-menu)
  ;;
esac
EOF
  chmod +x "${FAKE_BIN}/tmux"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function install_provider() {
  local provider="$1"

  cat >"${FAKE_BIN}/${provider}" <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x "${FAKE_BIN}/${provider}"
}

function install_all_providers() {
  local provider
  for provider in "${PROVIDERS[@]}"; do
    install_provider "${provider}"
  done
}

function menu_index() {
  local target="$1"
  local index=0
  local provider
  for provider in "${MENU_ORDER[@]}"; do
    if [[ "${provider}" == "${target}" ]]; then
      printf '%s\n' "${index}"
      return 0
    fi
    index=$((index + 1))
  done
  return 1
}

function run_tmux_ai_window() {
  PATH="${FAKE_BIN}:${SYSTEM_PATH}" \
    TMUX_CALLS_FILE="${TMUX_CALLS_FILE}" \
    TMUX_FAKE_PANE_DIR="${TMUX_FAKE_PANE_DIR}" \
    bash "${TMUX_AI_WINDOW_SCRIPT}" "$@"
}

function tmux_calls() {
  cat "${TMUX_CALLS_FILE}" 2>/dev/null
}

function new_window_command() {
  awk '
    /^CALL:new-window$/ { in_new_window = 1; next }
    /^END$/ { in_new_window = 0 }
    in_new_window && /^ARG:cd / {
      sub(/^ARG:/, "")
      print
      exit
    }
  ' "${TMUX_CALLS_FILE}"
}

function display_menu_args() {
  awk '
    /^CALL:display-menu$/ { in_display_menu = 1; next }
    /^END$/ {
      if (in_display_menu) {
        exit
      }
    }
    in_display_menu { print }
  ' "${TMUX_CALLS_FILE}"
}

function display_menu_default_choice() {
  awk '
    /^CALL:display-menu$/ { in_display_menu = 1; next }
    /^END$/ { in_display_menu = 0 }
    in_display_menu && previous == "ARG:-C" {
      sub(/^ARG:/, "")
      print
      exit
    }
    in_display_menu { previous = $0 }
  ' "${TMUX_CALLS_FILE}"
}

function display_menu_provider_keys() {
  awk '
    /^ARG:#\[fg=/ { next_arg_is_key = 1; next }
    next_arg_is_key {
      sub(/^ARG:/, "")
      print
      next_arg_is_key = 0
    }
  ' < <(display_menu_args)
}

function display_menu_provider_names() {
  awk '
    /^ARG:#\[fg=/ {
      line = $0
      sub(/^ARG:#\[fg=[^]]*\]/, "", line)
      sub(/#\[fg=#565f89,nobold\].*$/, "", line)
      sub(/ +$/, "", line)
      print line
    }
  ' < <(display_menu_args)
}

function test_launch_grok_uses_max_effort_and_auto_approval() {
  install_provider grok
  local dir="${TEST_TMP}/project dir"
  mkdir -p "${dir}"

  run_tmux_ai_window --launch grok --dir "${dir}"

  local quoted_dir
  printf -v quoted_dir "%q" "${dir}"
  assert_contains "cd ${quoted_dir} && clear && grok --effort xhigh --always-approve" "$(new_window_command)"
}

function test_launch_muse_uses_pinned_model_ultra_effort_and_yolo() {
  install_provider muse
  local dir="${TEST_TMP}/project dir"
  mkdir -p "${dir}"

  run_tmux_ai_window --launch muse --dir "${dir}"

  assert_contains "muse --model muse-spark-1.2 --reasoning-effort ultra --yolo" "$(new_window_command)"
}

function test_launch_muse_never_uses_contributor_model() {
  # The contributor model trains on inputs and outputs, so interactive source
  # sessions must stay pinned to the non-contributor model.
  install_provider muse

  run_tmux_ai_window --launch muse --dir "${TEST_TMP}"

  assert_not_contains "contributor" "$(new_window_command)"
}

function test_menu_includes_grok_and_muse_rows_with_keys() {
  install_all_providers

  run_tmux_ai_window

  local menu
  menu="$(display_menu_args)"
  assert_contains "ARG:#[fg=#2ac3de,bold]grok      #[fg=#565f89,nobold] xAI" "${menu}"
  assert_contains "ARG:g" "${menu}"
  assert_contains "ARG:run-shell \"executable_tmux_ai_window --launch grok" "${menu}"
  assert_contains "ARG:#[fg=#4a9dff,bold]muse      #[fg=#565f89,nobold] Meta" "${menu}"
  assert_contains "ARG:m" "${menu}"
  assert_contains "ARG:run-shell \"executable_tmux_ai_window --launch muse" "${menu}"
}

function test_only_grok_installed_makes_grok_the_default_choice() {
  install_provider grok

  run_tmux_ai_window

  assert_same "$(menu_index grok)" "$(display_menu_default_choice)"
}

function test_launch_unknown_provider_exits_2() {
  assert_exit_code "2" "$(run_tmux_ai_window --launch bogus --dir "${TEST_TMP}" 2>&1)"
}

# Key uniqueness is what makes the menu sort deterministic, so this test is
# load-bearing for row ordering and not merely a nicety.
function test_provider_menu_keys_are_unique() {
  install_all_providers

  run_tmux_ai_window

  local keys
  keys="$(display_menu_provider_keys)"
  assert_same "$(printf '%s\n' "${keys}" | wc -l | tr -d ' ')" \
    "$(printf '%s\n' "${keys}" | sort -u | wc -l | tr -d ' ')"
}

function test_menu_rows_are_sorted_by_menu_key() {
  install_all_providers

  run_tmux_ai_window

  assert_same "$(printf 'a\nc\ng\nm\no\nq\nx')" "$(display_menu_provider_keys)"
}

function test_menu_rows_are_ordered_by_provider_name_matching_keys() {
  install_all_providers

  run_tmux_ai_window

  assert_same "$(printf '%s\n' "${MENU_ORDER[@]}")" "$(display_menu_provider_names)"
}

function test_claude_is_the_default_choice_even_when_not_the_first_row() {
  install_all_providers

  run_tmux_ai_window

  assert_same "$(menu_index claude)" "$(display_menu_default_choice)"
}

function test_claude_is_preferred_over_an_earlier_installed_provider() {
  install_provider agy
  install_provider claude

  run_tmux_ai_window

  assert_same "$(menu_index claude)" "$(display_menu_default_choice)"
}

function test_first_installed_provider_is_default_when_claude_is_missing() {
  install_provider qwen
  install_provider opencode

  run_tmux_ai_window

  assert_same "$(menu_index opencode)" "$(display_menu_default_choice)"
}
