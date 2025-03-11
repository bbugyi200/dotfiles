.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: test
test: test-unit ## Run ALL dotfile tests.

.PHONY: test-unit
test-unit:  ## Run dotfile unit-tests.
	busted ./home/dot_config/nvim/tests/unit
