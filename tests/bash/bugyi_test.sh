#!/bin/bash

source ./home/lib/bugyi.sh

# Flex the pyprintf() function.
function test_pyprintf() {
  assert_same "foo bar foo" "$(pyprintf "{0} {1} {0}" "foo" "bar")"
}

# Flex the log::info() function.
function test_log_info() {
  assert_contains "foo bar baz" "$(log::info "foo bar baz" 2>&1)"
}

# Flex the die() function.
function test_die() {
  bash -c "source ./home/lib/bugyi.sh && die -x 5 'foo bar %s' 'baz'"
  assert_same 5 $?
}
