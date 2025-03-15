.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: lint
lint: lint-llscheck  ## Run linters on dotfiles.

.PHONY: lint-llscheck
lint-llscheck: ## Run llscheck linter on dotfiles.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running llscheck linter on Lua files...         │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	llscheck --checklevel Hint ./home/dot_config/nvim
	llscheck --checklevel Hint ./tests/nvim

.PHONY: test
test: test-nvim test-bash ## Run ALL dotfile tests.

.PHONY: test-nvim
test-nvim:  ## Run Neovim tests using busted.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running Neovim tests using busted...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	busted -p _test ./tests/nvim

.PHONY: test-bash
test-bash:  ## Run bash tests using bashunit.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running bash tests using bashunit...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	bashunit ./tests/bash
