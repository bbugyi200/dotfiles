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
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running Neovim tests using busted...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	busted ./tests/nvim

.PHONY: test-bash
test-bash:  ## Run bash tests using bashunit.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running bash tests using bashunit...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	bashunit ./tests/bash
