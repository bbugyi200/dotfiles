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

function expected_provider_description() {
  case "$1" in
  claude)
    echo "Anthropic"
    ;;
  codex)
    echo "OpenAI"
    ;;
  agy)
    echo "Antigravity"
    ;;
  qwen)
    echo "Alibaba"
    ;;
  opencode)
    echo "SST"
    ;;
  grok)
    echo "xAI"
    ;;
  muse)
    echo "Meta"
    ;;
  esac
}

function expected_provider_accent() {
  case "$1" in
  claude)
    echo "#e0af68"
    ;;
  codex)
    echo "#9ece6a"
    ;;
  agy)
    echo "#7aa2f7"
    ;;
  qwen)
    echo "#bb9af7"
    ;;
  opencode)
    echo "#7dcfff"
    ;;
  grok)
    echo "#2ac3de"
    ;;
  muse)
    echo "#4a9dff"
    ;;
  esac
}

function expected_enabled_label() {
  local provider="$1"

  printf "#[fg=%s,bold]%-10s#[fg=#565f89,nobold] %s" \
    "$(expected_provider_accent "${provider}")" \
    "${provider}" \
    "$(expected_provider_description "${provider}")"
}

function expected_disabled_label() {
  local provider="$1"

  printf -- "-#[fg=#565f89,bold]%-10s#[fg=#565f89,nobold] %-11s#[fg=#565f89,nobold] (not installed)" \
    "${provider}" \
    "$(expected_provider_description "${provider}")"
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

function display_menu_items() {
  awk '
    /^ARG:-?#\[fg=/ {
      label = $0
      sub(/^ARG:/, "", label)

      getline key
      sub(/^ARG:/, "", key)

      getline command
      sub(/^ARG:/, "", command)

      print label "\t" key "\t" command
    }
  ' < <(display_menu_args)
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
  awk -F '\t' '{ print $2 }' < <(display_menu_items)
}

function display_menu_provider_names() {
  awk -F '\t' '
    {
      line = $1
      sub(/^-/, "", line)
      gsub(/#\[[^]]*\]/, "", line)
      split(line, parts, /[[:space:]]+/)
      print parts[1]
    }
  ' < <(display_menu_items)
}

function display_menu_row() {
  local target="$1"

  awk -F '\t' -v target="${target}" '
    {
      line = $1
      sub(/^-/, "", line)
      gsub(/#\[[^]]*\]/, "", line)
      split(line, parts, /[[:space:]]+/)
      if (parts[1] == target) {
        print
        exit
      }
    }
  ' < <(display_menu_items)
}

function display_menu_row_label() {
  display_menu_row "$1" | awk -F '\t' '{ print $1 }'
}

function display_menu_row_key() {
  display_menu_row "$1" | awk -F '\t' '{ print $2 }'
}

function display_menu_row_command() {
  display_menu_row "$1" | awk -F '\t' '{ print $3 }'
}

function assert_enabled_provider_row() {
  local provider="$1"

  assert_same "$(expected_enabled_label "${provider}")" "$(display_menu_row_label "${provider}")"
  assert_same "$(provider_menu_key "${provider}")" "$(display_menu_row_key "${provider}")"
  assert_contains "run-shell \"executable_tmux_ai_window --launch ${provider}" \
    "$(display_menu_row_command "${provider}")"
}

function assert_disabled_provider_row() {
  local provider="$1"

  assert_same "$(expected_disabled_label "${provider}")" "$(display_menu_row_label "${provider}")"
  assert_same "" "$(display_menu_row_key "${provider}")"
  assert_same "" "$(display_menu_row_command "${provider}")"
}

function provider_menu_key() {
  case "$1" in
  agy)
    echo "a"
    ;;
  claude)
    echo "c"
    ;;
  grok)
    echo "g"
    ;;
  muse)
    echo "m"
    ;;
  opencode)
    echo "o"
    ;;
  qwen)
    echo "q"
    ;;
  codex)
    echo "x"
    ;;
  esac
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

function test_partial_install_menu_shows_complete_catalog_with_disabled_rows() {
  install_provider muse
  install_provider claude
  install_provider agy

  run_tmux_ai_window

  assert_same "$(printf '%s\n' "${MENU_ORDER[@]}")" "$(display_menu_provider_names)"
  assert_same "$(menu_index claude)" "$(display_menu_default_choice)"

  assert_enabled_provider_row agy
  assert_enabled_provider_row claude
  assert_enabled_provider_row muse

  assert_disabled_provider_row grok
  assert_disabled_provider_row opencode
  assert_disabled_provider_row qwen
  assert_disabled_provider_row codex
}

function test_only_grok_installed_makes_grok_the_default_choice() {
  install_provider grok

  run_tmux_ai_window

  assert_same "$(printf '%s\n' "${MENU_ORDER[@]}")" "$(display_menu_provider_names)"
  assert_same "$(menu_index grok)" "$(display_menu_default_choice)"
  assert_enabled_provider_row grok

  local provider
  for provider in agy claude muse opencode qwen codex; do
    assert_disabled_provider_row "${provider}"
  done
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

# tmux_ai_window is deployed to macOS too, where the `#!/bin/bash` shebang
# resolves to Apple's bash 3.2.57 (macOS cannot ship bash 4+, which is GPLv3).
# Bash 4-only builtins therefore fail at runtime there: a `mapfile` call once
# broke the menu with `line 48: mapfile: command not found` and left the user
# with a false "No AI agent CLI found" message. Every other test in this file
# runs under the host's bash (5.x on Linux and in CI) and so cannot catch that
# class of regression -- this static check is the only thing that can.
function test_script_avoids_bash_4_only_features() {
  local bash_4_only='(mapfile|readarray)'
  bash_4_only+='|(declare|local|typeset|readonly) +-[A-Za-z]*(A|n)([^A-Za-z]|$)'
  bash_4_only+='|\$\{[A-Za-z_][A-Za-z_0-9]*(\[[^]]*\])?(\^\^?|,,?|@[A-Za-z])'
  bash_4_only+='|;;&|\|&|&>>|wait +-n|globstar'

  # Comment lines are excluded so the script can name the builtins it avoids.
  assert_same "" \
    "$(grep -nE "${bash_4_only}" "${TMUX_AI_WINDOW_SCRIPT}" |
      grep -vE '^[0-9]+:[[:space:]]*#')"
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

function test_all_installed_menu_has_no_disabled_rows() {
  install_all_providers

  run_tmux_ai_window

  assert_not_contains "not installed" "$(display_menu_args)"
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

  assert_same "$(printf '%s\n' "${MENU_ORDER[@]}")" "$(display_menu_provider_names)"
  assert_same "$(menu_index claude)" "$(display_menu_default_choice)"
}

function test_first_installed_provider_is_default_when_claude_is_missing() {
  install_provider qwen
  install_provider opencode

  run_tmux_ai_window

  assert_same "$(printf '%s\n' "${MENU_ORDER[@]}")" "$(display_menu_provider_names)"
  assert_same "$(menu_index opencode)" "$(display_menu_default_choice)"
  assert_enabled_provider_row opencode
  assert_enabled_provider_row qwen

  local provider
  for provider in agy claude grok muse codex; do
    assert_disabled_provider_row "${provider}"
  done
}

function test_no_installed_providers_shows_message_without_menu() {
  run_tmux_ai_window

  local calls
  calls="$(tmux_calls)"
  assert_contains "ARG:No AI agent CLI found (claude/codex/agy/qwen/opencode/grok/muse)." "${calls}"
  assert_not_contains "CALL:display-menu" "${calls}"
}

function test_launch_known_missing_provider_exits_1() {
  assert_exit_code "1" "$(run_tmux_ai_window --launch codex --dir "${TEST_TMP}" 2>&1)"
  assert_contains "ARG:AI agent CLI is not installed: codex" "$(tmux_calls)"
}
