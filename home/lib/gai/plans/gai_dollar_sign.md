# Plan: Split HOOKS "!" Prefix into "!" and "$"

## Summary
Split the dual functionality of the "!" prefix:
- **"!" prefix**: No fix-hook agent runs when hook fails (appends auto-skip suffix)
- **"$" prefix** (new): Hook is NOT run for proposed HISTORY entries

When combined: "!$command" (e.g., "!$bb_hg_presubmit")

## Files to Modify

### 1. `home/lib/gai/work/changespec.py` (lines 136-168)
**HookEntry class** - Update prefix handling:
- Update docstring to document both prefixes
- Update `display_command` property: `return self.command.lstrip("!$")`
- Update `run_command` property: `return self.command.lstrip("!$")`
- Add `skip_fix_hook` property → checks for "!" in prefix
- Add `skip_proposal_runs` property → checks for "$" in prefix

### 2. `home/lib/gai/work/hooks/core.py` (line 92)
**`hook_needs_run()` function** - Change proposal check:
- Change `hook.command.startswith("!")` to `hook.skip_proposal_runs`

### 3. `home/lib/gai/work/hooks/operations.py` (line 435)
**`check_hook_completion()` function** - Update "!" check:
- Change `hook.command.startswith("!")` to `hook.skip_fix_hook`

### 4. `home/lib/gai/work/loop/hooks_runner.py` (line 298)
**`_start_stale_hooks_for_proposal()`** - Change proposal check:
- Change `hook.command.startswith("!")` to `hook.skip_proposal_runs`

### 5. `home/lib/gai/commit_workflow.py` (line 673)
**Auto-add hook**:
- Change `"!bb_hg_presubmit"` to `"!$bb_hg_presubmit"`
- Update comment on line 672

### 6. `home/lib/gai/loop_fix_hook_runner.py` (line 35)
**`_strip_hook_prefix()` helper**:
- Change to `return hook_command.lstrip("!$")`

### 7. `home/lib/gai/work/handlers/workflow_handlers.py` (line 59)
**`_strip_hook_prefix()` helper**:
- Change to `return hook_command.lstrip("!$")`
- Update docstring

## Tests to Add (`home/lib/gai/test/test_hooks.py`)

Add tests for the new prefix properties:
```python
def test_hook_entry_skip_fix_hook_with_exclamation() -> None:
    """Test skip_fix_hook is True when command starts with '!'."""
    hook = HookEntry(command="!some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is False

def test_hook_entry_skip_proposal_runs_with_dollar() -> None:
    """Test skip_proposal_runs is True when command has '$' prefix."""
    hook = HookEntry(command="$some_command")
    assert hook.skip_proposal_runs is True
    assert hook.skip_fix_hook is False

def test_hook_entry_combined_prefixes() -> None:
    """Test both prefixes work together as '!$'."""
    hook = HookEntry(command="!$some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is True
    assert hook.display_command == "some_command"
    assert hook.run_command == "some_command"

def test_hook_entry_display_command_strips_all_prefixes() -> None:
    """Test display_command strips both '!' and '$' prefixes."""
    assert HookEntry(command="!cmd").display_command == "cmd"
    assert HookEntry(command="$cmd").display_command == "cmd"
    assert HookEntry(command="!$cmd").display_command == "cmd"
    assert HookEntry(command="cmd").display_command == "cmd"
```

## Implementation Order
1. Update `HookEntry` in `changespec.py` with new properties
2. Update `_strip_hook_prefix` helpers in both locations
3. Update `hook_needs_run()` in `core.py` to use `skip_proposal_runs`
4. Update `_start_stale_hooks_for_proposal()` in `hooks_runner.py`
5. Update `check_hook_completion()` in `operations.py` to use `skip_fix_hook`
6. Update `commit_workflow.py` to use "!$bb_hg_presubmit"
7. Add tests to `test_hooks.py`
8. Run `make fix`, `make lint`, `make test`
9. Run `chezmoi apply`
