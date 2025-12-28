# Plan: Multi-Proposal Accept Support for `gai cl accept`

## Summary
Modify `gai cl accept` to accept multiple proposal entries with the syntax:
```
gai cl accept <id1>[(<msg1>)] [<id2>[(<msg2>)]] ...
```

Example: `gai cl accept 2b(Add foobar field) 2a 2c(Add baz field)`

## Files to Modify

### 1. `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/accept_workflow.py`

**Add new parser function** (~line 29, after `_parse_proposal_id`):
```python
def parse_proposal_entries(args: list[str]) -> list[tuple[str, str | None]] | None:
    """Parse proposal entry arguments into (id, msg) tuples.

    Supports:
    - New syntax: "2b(Add foobar field)" - id with optional message in parentheses
    - Legacy syntax: "2b" followed by optional separate message argument
    """
```
- Use regex pattern `r"^(\d+[a-z])(?:\((.+)\))?$"` to match `<id>[(<msg>)]`
- Handle backward compatibility for legacy `gai cl accept 2a "msg"` syntax

**Modify `_renumber_history_entries`** (line 246):
- Change `extra_msg: str | None` parameter to `extra_msgs: list[str | None] | None`
- Update logic around line 373 to apply per-proposal messages

**Modify `AcceptWorkflow.__init__`** (line 443):
- Change `proposal: str` to `proposals: list[tuple[str, str | None]]`
- Remove separate `msg` parameter

**Refactor `AcceptWorkflow.run()`** (line 472):
1. Validate ALL proposals upfront (exist, have DIFFs) before making changes
2. Claim workspace once
3. Loop through proposals in order:
   - Apply diff with `apply_diff_to_workspace()`
   - Amend commit with `bb_hg_amend`
   - On any failure: clean workspace and return False (fail-fast)
4. Call `_renumber_history_entries` once with all accepted proposals
5. Release workspace in finally block

### 2. `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/main.py`

**Modify argument parser** (lines 100-109):
```python
# Replace single proposal + optional msg with:
accept_parser.add_argument(
    "proposals",
    nargs="+",
    help="Proposal entries to accept. Format: <id>[(<msg>)]. "
    "Examples: '2a', '2b(Add foobar field)'.",
)
```

**Modify handler** (lines 610-617):
```python
if args.cl_command == "accept":
    from gai.accept_workflow import parse_proposal_entries

    entries = parse_proposal_entries(args.proposals)
    if entries is None:
        print_status("Invalid proposal entry format", "error")
        sys.exit(1)

    workflow = AcceptWorkflow(proposals=entries, cl_name=args.cl_name)
    success = workflow.run()
    sys.exit(0 if success else 1)
```

### 3. `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/test/test_accept_workflow.py`

**Add tests for `parse_proposal_entries`**:
- Single entry with message: `["2a(Add foobar)"]` -> `[("2a", "Add foobar")]`
- Single entry without message: `["2a"]` -> `[("2a", None)]`
- Multiple entries: `["2b(Add foobar)", "2a", "2c(Fix typo)"]`
- Legacy syntax: `["2a", "some message"]` -> `[("2a", "some message")]`
- Invalid format returns None
- Empty list returns None

**Add tests for multi-proposal `_renumber_history_entries`**:
- Multiple proposals with per-proposal messages

## Implementation Order

1. Add `parse_proposal_entries()` function + tests
2. Modify `_renumber_history_entries()` for per-proposal messages + tests
3. Refactor `AcceptWorkflow` class (init + run)
4. Update argument parser and handler in main.py
5. Run `make fix`, `make lint`, `make test`
6. Run `chezmoi apply`

## Backward Compatibility

- `gai cl accept 2a` - works (single, no message)
- `gai cl accept 2a "msg"` - works (legacy syntax)
- `gai cl accept 2a(msg)` - new syntax
- `gai cl accept 2a 2b(msg) 2c` - new multi-proposal feature

## Error Handling

Fail-fast behavior:
1. Validate all proposal IDs are valid format
2. Validate all proposals exist in HISTORY
3. Validate all proposals have DIFF paths
4. On any diff apply or amend failure, clean workspace and abort
