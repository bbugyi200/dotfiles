# chezmoi task runner

venv_dir := ".venv"
venv_bin := venv_dir / "bin"
venv_dir_abs := if venv_dir =~ "^/" { venv_dir } else { justfile_directory() / venv_dir }
venv_bin_abs := venv_dir_abs / "bin"
keep_sorted_version := "v0.8.0"
keep_sorted_bin := venv_bin / "keep-sorted"

default:
    @just --list

# Bootstrap .venv if it doesn't exist
_venv:
    @[ -x {{ venv_bin }}/python ] || uv venv {{ venv_dir }}

# Bootstrap .venv and install deps if stale
_setup: _venv
    @[ {{ venv_dir }}/.installed -nt requirements-dev.txt ] || (uv pip install -r requirements-dev.txt && touch {{ venv_dir }}/.installed)

# Bootstrap keep-sorted into the project venv so lint/fix do not depend on a
# user-global Go bin directory being present on PATH.
_setup-keep-sorted: _venv
    @if [ ! -x "{{ keep_sorted_bin }}" ]; then \
        if command -v keep-sorted > /dev/null 2>&1; then \
            printf "[setup] Linking keep-sorted from PATH into {{ keep_sorted_bin }}.\n"; \
            ln -sf "$(command -v keep-sorted)" "{{ keep_sorted_bin }}"; \
        elif command -v go > /dev/null 2>&1; then \
            printf "[setup] Installing keep-sorted {{ keep_sorted_version }} into {{ venv_bin }}.\n"; \
            GOBIN="{{ venv_bin_abs }}" CGO_ENABLED=0 go install github.com/google/keep-sorted@{{ keep_sorted_version }}; \
        else \
            printf "error: keep-sorted is required. Install it or install Go so this recipe can bootstrap github.com/google/keep-sorted@{{ keep_sorted_version }}.\n" >&2; \
            exit 127; \
        fi; \
    fi

# Print a box header for a top-level command (private helper)
_header NAME:
    @printf "\n"
    @printf "┌───────────────────────────────────────────────────────┐\n"
    @printf "│                RUNNING: just %-25s│\n" "{{ NAME }}"
    @printf "└───────────────────────────────────────────────────────┘\n"

# Auto-format all code (Python, Lua, Markdown)
fmt: (_header "fmt") fmt-py fmt-lua fmt-md

# Auto-format all code and fix keep-sorted blocks
fix: fmt fix-keep-sorted

# Auto-format Python code
fmt-py: _setup
    @printf "\n---------- Fixing Python with ruff... ----------\n"
    {{ venv_bin }}/ruff check --fix home/lib
    @printf "\n---------- Formatting Python with ruff... ----------\n"
    {{ venv_bin }}/ruff format home/lib

# Format Lua files with stylua
fmt-lua:
    @printf "\n---------- Formatting Lua files with stylua... ----------\n"
    stylua ./home/dot_config/nvim ./home/dot_hammerspoon ./tests/nvim ./tests/hammerspoon ./home/lib

# Format Markdown files with prettier
fmt-md:
    @printf "\n---------- Formatting Markdown with prettier... ----------\n"
    prettier --write --prose-wrap=always --print-width=120 "**/*.md"

# Auto-fix keep-sorted blocks in YAML files
fix-keep-sorted: _setup-keep-sorted
    @printf "\n---------- Fixing keep-sorted blocks in YAML files... ----------\n"
    git ls-files '*.yml' '*.yaml' | xargs {{ keep_sorted_bin }}

# Check all formatting (CI mode)
fmt-check: (_header "fmt-check") fmt-py-check fmt-md-check

# Check Python formatting (CI mode)
fmt-py-check: _setup
    @printf "\n---------- Checking Python formatting with ruff... ----------\n"
    {{ venv_bin }}/ruff format --check home/lib

# Check Markdown formatting (CI mode)
fmt-md-check:
    @printf "\n---------- Checking Markdown formatting with prettier... ----------\n"
    prettier --check --prose-wrap=always --print-width=120 "**/*.md"

# Run all linters
lint: (_header "lint") lint-keep-sorted lint-py lint-lua lint-md

# Run Python linters (ruff + mypy)
lint-py: _setup
    @printf "\n---------- Running ruff linter on Python files... ----------\n"
    {{ venv_bin }}/ruff check home/lib
    @printf "\n---------- Checking Python formatting with ruff... ----------\n"
    {{ venv_bin }}/ruff format --check home/lib
    @printf "\n---------- Running mypy on Python files... ----------\n"
    {{ venv_bin }}/mypy home/lib/xfile

# Run Lua linters (llscheck + luacheck)
lint-lua:
    @printf "\n---------- Running llscheck linter on Lua files... ----------\n"
    llscheck --checklevel Hint ./home/dot_config/nvim
    llscheck --checklevel Hint ./tests/nvim
    llscheck --checklevel Hint ./home/lib
    @printf "\n---------- Running luacheck linter on Lua files... ----------\n"
    luacheck --no-global ./home/dot_config/nvim ./tests/nvim ./home/lib

# Check Markdown formatting with prettier
lint-md:
    @printf "\n---------- Checking Markdown formatting with prettier... ----------\n"
    prettier --check --prose-wrap=always --print-width=120 "**/*.md"

# Lint keep-sorted blocks in YAML files (CI mode)
lint-keep-sorted: _setup-keep-sorted
    @printf "\n---------- Checking keep-sorted blocks in YAML files... ----------\n"
    git ls-files '*.yml' '*.yaml' | xargs {{ keep_sorted_bin }} --mode lint

# Run all tests
test: _setup (_header "test") test-nvim test-hammerspoon test-bash test-python

# Run Neovim tests using busted
test-nvim:
    @printf "\n---------- Running Neovim tests using busted... ----------\n"
    busted -p _test ./tests/nvim

# Run pure-Lua Hammerspoon request-model tests using busted
test-hammerspoon:
    @printf "\n---------- Running Hammerspoon tests using busted... ----------\n"
    busted ./tests/hammerspoon

# Run bash tests using bashunit
test-bash:
    @printf "\n---------- Running bash tests using bashunit... ----------\n"
    bashunit ./tests/bash

# Run Python tests using pytest
test-python: _setup
    @printf "\n---------- Running Python tests using pytest... ----------\n"
    cd home/lib/xfile && ../../../{{ venv_bin }}/pytest test

# Run all checks (format check + lint + test)
check: fmt-check lint test

# Remove build artifacts
clean:
    rm -rf {{ venv_dir }} .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage
