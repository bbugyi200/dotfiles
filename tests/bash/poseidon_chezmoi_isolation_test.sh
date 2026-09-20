#!/bin/bash

#################################################################################
# Render Athena-only chezmoi templates as if hostname were Mac or Apollo so     #
# those machines cannot acquire Poseidon Cargo settings.                        #
#################################################################################

function render_ignore() {
  local host="$1"
  sed "s/\\.chezmoi\\.hostname/\"${host}\"/g" home/.chezmoiignore |
    chezmoi execute-template
}

function render_cargo() {
  local host="$1"
  sed "s/\\.chezmoi\\.hostname/\"${host}\"/g" home/dot_cargo/config.toml.tmpl |
    chezmoi execute-template
}

function test_apollo_ignores_poseidon_files() {
  local rendered
  rendered="$(render_ignore apollo)"
  assert_contains ".cargo/config.toml" "${rendered}"
  assert_contains "bin/sase-rustc-wrapper" "${rendered}"
  assert_contains "poseidon-cache-watch.timer" "${rendered}"
}

function test_mac_ignores_poseidon_files() {
  local rendered
  rendered="$(render_ignore Kellys-MacBook-Pro)"
  assert_contains ".cargo/config.toml" "${rendered}"
  assert_contains "bin/poseidon-cache-watch" "${rendered}"
}

function test_athena_does_not_ignore_poseidon_files() {
  local rendered
  rendered="$(render_ignore athena)"
  assert_not_contains ".cargo/config.toml" "${rendered}"
  assert_not_contains "bin/sase-rustc-wrapper" "${rendered}"
}

function test_cargo_config_renders_only_on_athena() {
  local athena apollo mac
  athena="$(render_cargo athena)"
  apollo="$(render_cargo apollo)"
  mac="$(render_cargo Kellys-MacBook-Pro)"
  assert_contains "build-dir" "${athena}"
  assert_contains "cargo-{workspace-path-hash}" "${athena}"
  assert_contains "sase-rustc-wrapper" "${athena}"
  assert_not_contains "target-dir" "${athena}"
  assert_equals "" "${apollo}"
  assert_equals "" "${mac}"
}
