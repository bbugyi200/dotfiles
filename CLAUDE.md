# Claude Code Guidelines

## Quality Checks

**IMPORTANT**: After making ANY changes to code, ALWAYS run these targets in order:

1. **`make fix`** - Auto-fix linting issues and format code (ruff, black, stylua)
2. **`make lint`** - Verify all linting passes (llscheck, luacheck, ruff, mypy, flake8, black)
3. **`make test`** - Run all tests (nvim, bash, python)

If any of these fail, fix the issues before completing the task. Do NOT skip these steps.

## Core Rules

1. **Private functions/methods/classes**: ALWAYS prefix with underscore (`_`)
2. **Type annotations**: ALWAYS annotate ALL function parameters and return types
3. **Shared utilities**: NEVER put single-use functions in shared modules - move them to their only consumer as private functions
4. **Private function imports**: NEVER import private functions (prefixed with `_`) across modules - make them public if they need to be shared

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
