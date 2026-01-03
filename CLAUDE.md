## Quality Checks

**IMPORTANT**: After making ANY changes to code, ALWAYS run these targets in order:

1. **`make fix`** - Auto-fix linting issues and format code (ruff, black, stylua)
2. **`make lint`** - Verify all linting passes (llscheck, luacheck, ruff, mypy, flake8, black)
3. **`make test`** - Run all tests (nvim, bash, python)

If any of these fail, fix the issues before completing the task. Do NOT skip these steps.

**CRITICAL**: NEVER leave `make lint` or `make test` in a broken state. If you introduce changes that cause linting or test failures, you MUST fix them before completing your work. This includes:
- Fixing any mypy type errors you introduce
- Ensuring test coverage remains at or above the required threshold
- Fixing any new test failures caused by your changes
- Addressing any linting issues (ruff, flake8, black, etc.)

## Chezmoi

**CRITICAL**: This repository uses chezmoi to manage dotfiles. After making ANY changes to files in the chezmoi directory, you MUST run:

```bash
chezmoi apply
```

Changes will NOT take effect until applied. The files you edit are in `/Users/bbugyi/.local/share/chezmoi/home/`, but the actual files used by the system are in the home directory (e.g., `~/.config/nvim/`, `~/.local/bin/`).

**Workflow**:
1. Edit files in `/Users/bbugyi/.local/share/chezmoi/home/`
2. Run quality checks (`make fix`, `make lint`, `make test`)
3. Run `chezmoi apply` to sync changes to the actual home directory
4. Test the changes in the actual environment
