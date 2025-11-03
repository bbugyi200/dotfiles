## Quality Checks

**IMPORTANT**: After making ANY changes to code, ALWAYS run these targets in order:

1. **`make fix`** - Auto-fix linting issues and format code (ruff, black, stylua)
2. **`make lint`** - Verify all linting passes (llscheck, luacheck, ruff, mypy, flake8, black)
3. **`make test`** - Run all tests (nvim, bash, python)

If any of these fail, fix the issues before completing the task. Do NOT skip these steps.

### Pre-commit Hook

A pre-commit hook is configured to automatically run `make fix` before each commit. This ensures code is always formatted and auto-fixable issues are resolved before committing.

**Setup**: Run `./scripts/setup-git-hooks.sh` to configure the hooks (already done in this repo).

**Behavior**: The hook will:
- Run `make fix` automatically
- Stage any files that were modified by formatters
- Prevent commit if `make fix` fails

To bypass the hook (not recommended): `git commit --no-verify`

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
