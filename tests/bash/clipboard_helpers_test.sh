#!/bin/bash

#################################################################################
# Static checks that Mac clipboard readers/helpers go through xp/xc.            #
#################################################################################

ALIASES="${PWD}/home/dot_config/aliases.sh"
GCL="${PWD}/home/bin/executable_gcl"
PASTE_PARTS="${PWD}/home/bin/executable_paste_parts"
ZOTXC="${PWD}/home/bin/executable_zotxc"
SHARED_LUA="${PWD}/home/dot_config/nvim/lua/plugins/codecompanion/slash_cmds/shared.lua"

function test_aliases_read_mac_clipboard_via_xp() {
  local contents
  contents="$(cat "${ALIASES}")"

  assert_contains 'mov() { tman add -w "${MOV}" "${1:-"$(xp)"}"; }' "${contents}"
  assert_contains 'tv() { tman add -w "${TV}" "${1:-"$(xp)"}"; }' "${contents}"
  assert_contains 'tsm-mov() { tsm-add "${@:-$(xp)}" -w "$MOV"; }' "${contents}"
  assert_contains 'tsm-tv() { tsm-add "${@:-$(xp)}" -w "$TV"; }' "${contents}"
  assert_contains 'xp >"${temp_file}"' "${contents}"
  assert_contains 'xco() { xp; }' "${contents}"
  assert_contains 'GET_CLIP="xp"' "${contents}"
}

function test_clip2mac_and_clip3mac_avoid_stale_mac_alias() {
  local contents
  contents="$(cat "${ALIASES}")"

  assert_contains 'alias clip2mac='"'"'tmux save-buffer - | tee /dev/stderr | ssh -x -T -o BatchMode=yes -o ConnectTimeout=3 "${CLIP_PEER:-mac}" pbcopy'"'" "${contents}"
  assert_contains "alias clip3mac='xp | tee /dev/stderr | tmux load-buffer -'" "${contents}"
  assert_not_contains 'mac pbcopy' "${contents}"
  assert_not_contains 'mac pbpaste' "${contents}"
}

function test_hera_aliases_still_target_lan_x_display() {
  local contents
  contents="$(cat "${ALIASES}")"

  assert_contains "alias clip2hera='DISPLAY=:0 xclip -o -sel clip | tee /dev/stderr | hera DISPLAY=:0 xclip -sel clip'" "${contents}"
  assert_contains "alias clip3hera='hera DISPLAY=:0 xclip -o -sel clip | tee /dev/stderr | DISPLAY=:0 xclip -sel clip'" "${contents}"
}

function test_gcl_and_paste_parts_use_xp_and_xc() {
  assert_contains $'function paste_clip() {\n  xp\n}' "$(cat "${GCL}")"
  assert_not_contains 'xclip' "$(cat "${GCL}")"
  assert_contains $'function paste_clip() {\n  xp\n}' "$(cat "${PASTE_PARTS}")"
  assert_contains $'function copy_clip() {\n  xc\n}' "$(cat "${PASTE_PARTS}")"
  assert_not_contains 'xclip' "$(cat "${PASTE_PARTS}")"
}

function test_zotxc_copies_via_xc() {
  assert_contains 'zorg template "$@" | xc' "$(cat "${ZOTXC}")"
  assert_not_contains 'xclip' "$(cat "${ZOTXC}")"
  assert_not_contains 'pbcopy' "$(cat "${ZOTXC}")"
}

function test_codecompanion_non_macos_clipboard_uses_xp() {
  local contents
  contents="$(cat "${SHARED_LUA}")"

  assert_contains 'clipboard_cmd = "xp"' "${contents}"
  assert_not_contains 'xclip' "${contents}"
}
