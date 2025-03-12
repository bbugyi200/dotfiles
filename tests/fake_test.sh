#!/bin/bash

function set_up() {
  touch /tmp/temp_file.txt
  printf "foobar" >/tmp/temp_file.txt
}

function tear_down() {
  rm /tmp/temp_file.txt
}

function test_bazbuz() {
  printf " bazbuz\n" >>/tmp/temp_file.txt
  assert_same "foobar bazbuz" "$(cat /tmp/temp_file.txt)"
}
