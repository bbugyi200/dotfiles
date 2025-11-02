.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: lint
lint: lint-llscheck lint-luacheck lint-python ## Run linters on dotfiles.

.PHONY: lint-llscheck
lint-llscheck: ## Run llscheck linter on dotfiles.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running llscheck linter on Lua files...         │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	llscheck --checklevel Hint ./home/dot_config/nvim
	llscheck --checklevel Hint ./tests/nvim
	llscheck --checklevel Hint ./home/lib

.PHONY: lint-luacheck
lint-luacheck: ## Run luacheck linter on dotfiles.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running luacheck linter on Lua files...         │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	luacheck --no-global ./home/dot_config/nvim ./tests/nvim ./home/lib

VENV_DIR := .venv
PYTHON := python3
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

.PHONY: lint-python
lint-python: $(VENV_DIR) ## Run Python linters on dotfiles.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running ruff linter on Python files...          │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(VENV_DIR)/bin/ruff check home/lib
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running ruff format check on Python files...    │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(VENV_DIR)/bin/ruff format --check home/lib
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running mypy on Python files...                 │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(VENV_DIR)/bin/mypy --explicit-package-bases home/lib
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running flake8 on Python files...               │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(VENV_DIR)/bin/flake8 home/lib
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running black check on Python files...          │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(VENV_DIR)/bin/black --check home/lib

$(VENV_DIR): requirements-dev.txt
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Creating virtual environment...                 │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements-dev.txt
	@touch $(VENV_DIR)

.PHONY: test
test: test-nvim test-bash ## Run ALL dotfile tests.

.PHONY: test-nvim
test-nvim: ## Run Neovim tests using busted.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running Neovim tests using busted...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	@printf "\n"
	busted -p _test ./tests/nvim

.PHONY: test-bash
test-bash: ## Run bash tests using bashunit.
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│   >>> Running bash tests using bashunit...            │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"
	bashunit ./tests/bash
