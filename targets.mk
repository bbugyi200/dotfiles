.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: lint
lint:  ## Run linters on dotfiles.
	@echo TODO: Implement lint target.

.PHONY: test
test: test-nvim test-bash ## Run ALL dotfile tests.

.PHONY: test-nvim
test-nvim:  ## Run Neovim tests using busted.
	@printf "\n>>> Running Neovim tests using busted...\n"
	busted ./home/dot_config/nvim/lua/tests

.PHONY: test-bash
test-bash:  ## Run bash tests using bashunit.
	@printf "\n>>> Running bash tests using bashunit...\n"
	bashunit ./tests
