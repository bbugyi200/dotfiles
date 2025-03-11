.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: lint
lint:  ## Run linters on dotfiles.
	@echo TODO: Implement lint target.

.PHONY: test
test: test-e2e test-unit ## Run ALL dotfile tests.

.PHONY: test-e2e
test-e2e:  ## Run dotfile end-to-end tests.
	busted ./home/dot_config/nvim/lua/tests/e2e.lua

.PHONY: test-unit
test-unit:  ## Run dotfile unit-tests.
	busted ./home/dot_config/nvim/lua/tests/unit.lua
