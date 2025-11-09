.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: fix-header
fix-header:
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│                  RUNNING: make fix                    │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"

.PHONY: fix
fix: fix-header fix-python fix-lua ## Fix and format Python and Lua files.

.PHONY: lint-header
lint-header:
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│                  RUNNING: make lint                   │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"

.PHONY: lint
lint: lint-header lint-llscheck lint-luacheck lint-python ## Run linters on dotfiles.

.PHONY: lint-llscheck
lint-llscheck: ## Run llscheck linter on dotfiles.
	@printf "\n---------- Running llscheck linter on Lua files... ----------\n"
	llscheck --checklevel Hint ./home/dot_config/nvim
	llscheck --checklevel Hint ./tests/nvim
	llscheck --checklevel Hint ./home/lib

.PHONY: lint-luacheck
lint-luacheck: ## Run luacheck linter on dotfiles.
	@printf "\n---------- Running luacheck linter on Lua files... ----------\n"
	luacheck --no-global ./home/dot_config/nvim ./tests/nvim ./home/lib

VENV_DIR := .venv
PYTHON := python3.12
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

.PHONY: lint-python
lint-python: $(VENV_DIR) ## Run Python linters on dotfiles.
	@printf "\n---------- Running ruff linter on Python files... ----------\n"
	$(VENV_DIR)/bin/ruff check home/lib
	@printf "\n---------- Running ruff format check on Python files... ----------\n"
	$(VENV_DIR)/bin/ruff format --check home/lib
	@printf "\n---------- Running mypy on Python files... ----------\n"
	$(VENV_DIR)/bin/mypy --explicit-package-bases home/lib
	@printf "\n---------- Running flake8 on Python files... ----------\n"
	$(VENV_DIR)/bin/flake8 home/lib
	@printf "\n---------- Running black check on Python files... ----------\n"
	$(VENV_DIR)/bin/black --check home/lib
	@printf "\n---------- Checking Python file line limits... ----------\n"
	~/bin/pylimit home/lib 750
	@printf "\n---------- Checking for unused Python definitions... ----------\n"
	$(VENV_PYTHON) home/bin/executable_unused_pydefs home/lib/gai
	$(VENV_PYTHON) home/bin/executable_unused_pydefs home/lib/xfile

$(VENV_DIR): requirements-dev.txt
	@printf "\n---------- Creating virtual environment... ----------\n"
	@# Remove old venv if it exists with wrong Python version
	@if [ -f $(VENV_DIR)/bin/python ]; then \
		VENV_VERSION=$$($(VENV_DIR)/bin/python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1); \
		if [ "$$VENV_VERSION" != "3.12" ]; then \
			echo "Removing old venv (Python $$VENV_VERSION)..."; \
			rm -rf $(VENV_DIR); \
		fi; \
	fi
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements-dev.txt
	@touch $(VENV_DIR)

.PHONY: fix-python
fix-python: $(VENV_DIR) ## Fix and format Python files with ruff and black.
	@printf "\n---------- Running 'ruff check --fix' on Python files... ----------\n"
	$(VENV_DIR)/bin/ruff check --fix home/lib
	@printf "\n---------- Running 'ruff format' on Python files... ----------\n"
	$(VENV_DIR)/bin/ruff format home/lib
	@printf "\n---------- Formatting Python files with black... ----------\n"
	$(VENV_DIR)/bin/black home/lib

.PHONY: fix-lua
fix-lua: ## Format Lua files with stylua.
	@printf "\n---------- Formatting Lua files with stylua... ----------\n"
	stylua ./home/dot_config/nvim ./tests/nvim ./home/lib

.PHONY: test-header
test-header:
	@printf "\n"
	@printf "┌───────────────────────────────────────────────────────┐\n"
	@printf "│                  RUNNING: make test                   │\n"
	@printf "└───────────────────────────────────────────────────────┘\n"

.PHONY: test
test: test-header test-nvim test-bash test-python ## Run ALL dotfile tests.

.PHONY: test-nvim
test-nvim: ## Run Neovim tests using busted.
	@printf "\n---------- Running Neovim tests using busted... ----------\n"
	busted -p _test ./tests/nvim

.PHONY: test-bash
test-bash: ## Run bash tests using bashunit.
	@printf "\n---------- Running bash tests using bashunit... ----------\n"
	bashunit ./tests/bash

.PHONY: test-python
test-python: $(VENV_DIR) ## Run Python tests using pytest.
	@printf "\n---------- Running Python tests using pytest... ----------\n"
	cd home/lib/gai && ../../../$(VENV_DIR)/bin/pytest test
	cd home/lib/xfile && ../../../$(VENV_DIR)/bin/pytest test
