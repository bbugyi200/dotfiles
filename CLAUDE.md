# Claude Code Guidelines

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

## Core Rules

1. **Private functions/methods/classes**: ALWAYS prefix with underscore (`_`)
2. **Type annotations**: ALWAYS annotate ALL function parameters and return types
3. **Shared utilities**: NEVER put single-use functions in shared modules - move them to their only consumer as private functions
4. **Private function imports**: NEVER import private functions (prefixed with `_`) across modules - make them public if they need to be shared

## Testing Requirements

**CRITICAL**: Testing is mandatory for large Python projects.

### When Tests Are Required

1. **Project Size Threshold**: Any Python project (e.g., `home/lib/gai`) that exceeds **1000 lines of code** MUST have dedicated tests
   - Count includes all `.py` files in the project directory
   - Use `find home/lib/PROJECT -name "*.py" -exec wc -l {} + | tail -1` to check total lines

2. **New Features in Large Projects**: When adding new features to projects that already have tests (e.g., `home/lib/gai`), you MUST:
   - Add corresponding test coverage for the new feature
   - Update existing tests if the feature modifies existing behavior
   - Ensure `make test` passes before completing the task

### Test Guidelines

- Place tests in a `test/` directory within the project
- Name test files with `test_` prefix (e.g., `test_main.py`)
- Use **pytest** for Python tests
- Use **global `test_*` functions** (NOT nested in classes) in most cases
  - Classes should only be used for sharing fixtures or grouping highly related tests
  - Keep tests simple and flat by default
- Aim for meaningful test coverage, not just line coverage
- Test both happy paths and error cases
- Always add type annotations to test functions (return type should be `-> None`)

### Example

```python
# home/lib/gai/test/test_main.py
import pytest
from gai.main import normalize_spec


def test_normalize_spec_plus_format_unchanged() -> None:
    """Test that plus format is preserved."""
    assert normalize_spec("3+2") == "3+2"


def test_normalize_spec_invalid_format() -> None:
    """Test that invalid formats raise ValueError."""
    with pytest.raises(ValueError):
        normalize_spec("invalid")
```

## Examples

### Private Functions
```python
# ✅ Good
def _create_boxed_header(title: str) -> str:
    return f"=== {title} ==="

# ❌ Bad  
def create_boxed_header(title):  # Missing underscore and types
    return f"=== {title} ==="
```

### Shared vs Single-Use
```python
# ✅ Good - In the module that uses it
def _read_artifact_file(file_path: str) -> str:
    """Private function used only by this module."""
    with open(file_path) as f:
        return f.read()

# ❌ Bad - In shared_utils.py when only one module uses it
def read_artifact_file(file_path: str) -> str:
    with open(file_path) as f:
        return f.read()
```

### Type Annotations
```python
# ✅ Good
def process_data(items: list[str], max_count: int = 100) -> dict[str, int]:
    return {}

# ❌ Bad
def process_data(items, max_count=100):
    return {}
```
