# Implementation Plan: Multiple Test Targets Support

## Overview

Add support for specifying multiple test targets in the TEST TARGETS field using a multi-line format similar to DESCRIPTION, but without blank lines.

## Current Format

**Single-line, space-separated:**
```
TEST TARGETS: //my/package:test1 //other/package:test2
```

## Proposed Format

**Multi-line, 2-space indented (like DESCRIPTION, but no blank lines):**
```
TEST TARGETS:
  //my/package:test1
  //other/package:test2
  //third/package:integration_test
```

**Special values remain single-line:**
```
TEST TARGETS: None
```

## Implementation Steps

### 1. Update ChangeSpec Parsing (`workflow_nodes.py`)

**File:** `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Function:** `_parse_project_spec` (lines 1643-1708)

**Changes needed:**
- Modify parsing logic to handle TEST TARGETS like DESCRIPTION
- When TEST TARGETS field is encountered:
  - If the line contains a value (e.g., `TEST TARGETS: None`), treat as single-line
  - If the line is just `TEST TARGETS:`, collect subsequent 2-space indented lines
  - Continue until a non-indented line or blank line is encountered
  - **Critical:** Reject any blank lines within TEST TARGETS (unlike DESCRIPTION)
- Store internally as newline-separated string or list

**Backwards compatibility:**
- Must still support single-line format: `TEST TARGETS: //foo:bar //baz:qux`
- Detection: if line contains value after colon, parse as single-line

### 2. Update ChangeSpec Formatting (`workflow_nodes.py`)

**File:** `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Function:** `_format_changespec` (lines 1711-1741)

**Current code (line 1736):**
```python
if "TEST TARGETS" in cs:
    lines.append(f"TEST TARGETS: {cs['TEST TARGETS']}")
```

**New logic:**
```python
if "TEST TARGETS" in cs:
    test_targets = cs["TEST TARGETS"]
    if test_targets in ("None", "") or "\n" not in test_targets:
        # Single-line format for None, empty, or single target
        lines.append(f"TEST TARGETS: {test_targets}")
    else:
        # Multi-line format
        lines.append("TEST TARGETS:")
        for target in test_targets.split("\n"):
            target = target.strip()
            if target:  # Skip blank lines (defensive, shouldn't exist)
                lines.append(f"  {target}")
```

### 3. Update Rich Color Formatting (`workflow_nodes.py`)

**File:** `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Function:** `_format_changespec_with_colors` (lines 1795-1804)

**Current code:**
```python
# TEST TARGETS field (optional)
if "TEST TARGETS" in cs:
    test_targets = cs["TEST TARGETS"]
    add_field_key(result, "TEST TARGETS")
    result.append(" ")
    if test_targets and test_targets != "None":
        result.append(test_targets, style="bold #AFD75F")
    else:
        result.append("None", style="bold #AFD75F")
    result.append("\n")
```

**New logic:**
```python
# TEST TARGETS field (optional)
if "TEST TARGETS" in cs:
    test_targets = cs["TEST TARGETS"]

    # Check if single-line or multi-line format
    if test_targets in ("None", "") or "\n" not in test_targets:
        # Single-line format
        add_field_key(result, "TEST TARGETS")
        result.append(" ")
        if test_targets and test_targets != "None":
            result.append(test_targets, style="bold #AFD75F")
        else:
            result.append("None", style="bold #AFD75F")
        result.append("\n")
    else:
        # Multi-line format (like DESCRIPTION)
        add_field_key(result, "TEST TARGETS")
        result.append("\n")
        for target in test_targets.split("\n"):
            target = target.strip()
            if target:  # Skip blank lines (defensive)
                result.append(f"  {target}", style="bold #AFD75F")
                result.append("\n")
```

### 4. Update Test Target Extraction from Commands

**File:** `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Usage locations:**
- Line 882: `test_targets = selected_cs.get("TEST TARGETS", "").strip()`
- Line 1329: `test_targets_raw = selected_cs.get("TEST TARGETS", "").strip()`
- Line 1195: `test_cmd = f"rabbit test -c opt --no_show_progress {test_targets}"`

**Changes needed:**
- Create helper function to convert multi-line format to space-separated:
  ```python
  def _test_targets_to_command_args(test_targets: str) -> str:
      """Convert multi-line or single-line test targets to space-separated string."""
      if not test_targets or test_targets == "None":
          return test_targets

      # Split by newlines and filter out empty lines
      targets = [t.strip() for t in test_targets.split("\n")]
      targets = [t for t in targets if t and t != "None"]

      # Join with spaces for command line
      return " ".join(targets)
  ```

- Update all command construction sites to use this helper
- Line 1195 becomes: `test_cmd = f"rabbit test -c opt --no_show_progress {_test_targets_to_command_args(test_targets)}"`

### 5. Update Vim Syntax File (`gaiproject.vim`)

**File:** `home/dot_config/nvim/syntax/gaiproject.vim`

**Current TEST TARGETS syntax (lines 48-55):**
```vim
syn match GaiProjectTestTargetsLine "^TEST TARGETS:\s*\%(None\)\@!.\+$" contains=GaiProjectTestTargetsKey
syn match GaiProjectTestTargetsKey "^TEST TARGETS:" contained
syn match GaiProjectTestTargetsNone "^TEST TARGETS:\s*None\s*$" contains=GaiProjectTestTargetsNoneKey
syn match GaiProjectTestTargetsNoneKey "^TEST TARGETS:" contained
```

**New syntax (multi-line support + validation):**
```vim
" TEST TARGETS field - key line
syn match GaiProjectTestTargetsKey "^TEST TARGETS:" nextgroup=GaiProjectTestTargetsInline,GaiProjectTestTargetsNoneValue skipwhite
syn match GaiProjectTestTargetsNoneValue "\s*None\s*$" contained

" TEST TARGETS - single-line format (one or more valid bazel targets)
" Valid target format: //path/to/package:target_name
" Path can contain: a-z A-Z 0-9 _ / . -
" Target name can contain: a-z A-Z 0-9 _ -
syn match GaiProjectTestTargetsInline "\s*//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\%(\s\+//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\)*\s*$" contained

" TEST TARGETS - multi-line format (2-space indented lines, each a valid bazel target)
" Only highlight lines that match the valid bazel target pattern
syn match GaiProjectTestTargetsMultiLine "^\s\s//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\s*$"

" Highlight groups
highlight GaiProjectTestTargetsKey gui=bold guifg=#87D7FF
highlight GaiProjectTestTargetsNoneValue gui=bold guifg=#AFD75F
highlight GaiProjectTestTargetsInline gui=bold guifg=#AFD75F
highlight GaiProjectTestTargetsMultiLine gui=bold guifg=#AFD75F
```

**Key improvements:**
- Uses regex pattern `//[a-zA-Z0-9_/.-]+:[a-zA-Z0-9_-]+` to validate bazel targets
- Only highlights valid test targets (both single-line and multi-line)
- Invalid targets (wrong format) won't be highlighted
- Preserves "None" value highlighting

### 6. Update Agent Prompts

**File:** `home/lib/gai/new_failing_tests_workflow/prompts.py`

**Current format (lines 107-114):**
```
TEST_TARGETS: <target1> <target2> ...

Rules:
- Use space-separated bazel/rabbit test targets
```

**Updated format:**
```
TEST_TARGETS:
  <target1>
  <target2>

Rules:
- Each test target on its own line, 2-space indented
- Valid format: //path/to/package:target_name
- No blank lines between targets
- If only one target: can use single-line format (TEST_TARGETS: //path/to:test)
- If no tests needed: TEST_TARGETS: None
```

**File:** `home/lib/gai/create_project_workflow/prompts.py`

**Update similar format documentation around line 127**

### 7. Update Agent Parsing

**File:** `home/lib/gai/new_failing_tests_workflow/agents.py`

**Current extraction (lines 60-63):**
```python
elif line_stripped.startswith("TEST_TARGETS:"):
    # Extract test targets from the line
    test_targets = line_stripped[len("TEST_TARGETS:") :].strip()
```

**Updated to handle multi-line:**
```python
elif line_stripped.startswith("TEST_TARGETS:"):
    # Extract test targets (single or multi-line)
    inline_value = line_stripped[len("TEST_TARGETS:") :].strip()
    if inline_value:
        # Single-line format
        test_targets = inline_value
    else:
        # Multi-line format - collect indented lines
        targets = []
        for next_line in lines[i+1:]:
            if next_line.startswith("  "):
                target = next_line.strip()
                if target:
                    targets.append(target)
            elif next_line.strip():
                break  # Non-indented line, end of field
        test_targets = "\n".join(targets) if targets else ""
    print_status(f"Extracted test targets: {test_targets}", "info")
```

### 8. Update Documentation

**File:** `home/lib/gai/docs/change_spec.md`

**Current (line 11):**
```
TEST TARGETS: <TEST_TARGETS>  // Optional field. Either "None" (no tests required), one or more bazel/test targets (e.g., "//my/package:my_test"), or omitted (tests required but targets TBD)
```

**Updated:**
```
TEST TARGETS:  // Optional field. Either "None" (no tests required), or one or more bazel test targets
  // Formats supported:
  //   Single-line:  TEST TARGETS: //my/package:test1 //other:test2
  //   Multi-line:   TEST TARGETS:
  //                   //my/package:test1
  //                   //other/package:test2
  // Valid target format: //path/to/package:target_name
  // Can be omitted (tests required but targets TBD)
```

### 9. Update Tests

**File:** `home/lib/gai/test/test_work_projects_workflow.py`

**Add test cases:**

1. **Test parsing multi-line TEST TARGETS:**
```python
def test_parse_multiline_test_targets():
    spec = """
PROJECT: Test Project
DESCRIPTION:
  Test description

TEST TARGETS:
  //my/package:test1
  //other/package:test2
  //third:integration_test
"""
    cs = _parse_project_spec(spec)
    assert cs["TEST TARGETS"] == "//my/package:test1\n//other/package:test2\n//third:integration_test"
```

2. **Test backwards compatibility with single-line:**
```python
def test_parse_singleline_test_targets_backwards_compat():
    spec = """
PROJECT: Test Project
TEST TARGETS: //my/package:test1 //other/package:test2
"""
    cs = _parse_project_spec(spec)
    assert cs["TEST TARGETS"] == "//my/package:test1 //other/package:test2"
```

3. **Test formatting multi-line TEST TARGETS:**
```python
def test_format_multiline_test_targets():
    cs = {
        "PROJECT": "Test",
        "TEST TARGETS": "//my/package:test1\n//other/package:test2"
    }
    formatted = _format_changespec(cs)
    assert "TEST TARGETS:\n  //my/package:test1\n  //other/package:test2" in formatted
```

4. **Test command argument conversion:**
```python
def test_test_targets_to_command_args():
    # Multi-line to space-separated
    multi = "//my/package:test1\n//other/package:test2"
    assert _test_targets_to_command_args(multi) == "//my/package:test1 //other/package:test2"

    # Single-line unchanged
    single = "//my/package:test1 //other:test2"
    assert _test_targets_to_command_args(single) == single

    # None unchanged
    assert _test_targets_to_command_args("None") == "None"
```

5. **Test blank line rejection in parsing:**
```python
def test_parse_test_targets_rejects_blank_lines():
    spec = """
TEST TARGETS:
  //my/package:test1

  //other/package:test2
"""
    # Should stop at blank line or skip it
    cs = _parse_project_spec(spec)
    # Result should not contain blank line
    assert "\n\n" not in cs.get("TEST TARGETS", "")
```

### 10. Update Lua Snippets (Optional)

**File:** `home/dot_config/nvim/luasnippets/gaiproject.lua`

**Current TEST TARGETS snippet** may need updating to suggest multi-line format:
```lua
s("test_targets", {
  t("TEST TARGETS:"),
  i(1, "None"),
  -- Or multi-line option:
  -- t({"TEST TARGETS:", "  "}),
  -- i(1, "//path/to:target"),
}),
```

## Validation Rules

### Bazel/Blaze Test Target Format

**Valid pattern:** `//path/to/package:target_name`

**Component rules:**
- Must start with `//`
- Path segment: `[a-zA-Z0-9_/.-]+` (alphanumeric, underscore, slash, dot, hyphen)
- Separator: `:`
- Target name: `[a-zA-Z0-9_-]+` (alphanumeric, underscore, hyphen)

**Examples:**
- ✅ `//my/package:my_test`
- ✅ `//foo/bar/baz.qux:integration-test`
- ✅ `//tools:all`
- ❌ `my/package:test` (missing //)
- ❌ `//my/package` (missing :target)
- ❌ `//my package:test` (space in path)
- ❌ `//my/package:my test` (space in target)

## Edge Cases to Handle

1. **Empty field:** `TEST TARGETS:` with no following lines
   - Parse as empty string
   - Format as single-line when empty

2. **Single target in multi-line format:**
   ```
   TEST TARGETS:
     //my/package:test
   ```
   - Store as single-line internally (optimization)
   - Or keep as multi-line (consistency)

3. **Mixed whitespace:** Extra spaces before/after targets
   - Strip whitespace when parsing
   - Format with exactly 2 spaces

4. **"None" in multi-line format:**
   ```
   TEST TARGETS:
     None
   ```
   - Reject? Or normalize to single-line "None"?
   - Recommendation: normalize to `TEST TARGETS: None`

5. **Blank lines (CRITICAL - must reject):**
   ```
   TEST TARGETS:
     //my/package:test1

     //my/package:test2
   ```
   - Unlike DESCRIPTION, TEST TARGETS should NOT allow blank lines
   - Either reject the spec or stop parsing at blank line

## Migration Strategy

1. **No migration needed** - format is additive
2. **Existing single-line specs continue to work**
3. **Users can gradually adopt multi-line format**
4. **Auto-formatter could optionally convert single-line to multi-line when > N targets**

## Testing Checklist

- [ ] Parse single-line TEST TARGETS (backwards compat)
- [ ] Parse multi-line TEST TARGETS
- [ ] Parse TEST TARGETS: None
- [ ] Parse empty TEST TARGETS field
- [ ] Reject blank lines in TEST TARGETS
- [ ] Format single-line TEST TARGETS
- [ ] Format multi-line TEST TARGETS
- [ ] Format TEST TARGETS: None
- [ ] Rich color output for single-line
- [ ] Rich color output for multi-line
- [ ] Convert multi-line to command args (space-separated)
- [ ] Vim syntax highlighting for single-line valid targets
- [ ] Vim syntax highlighting for multi-line valid targets
- [ ] Vim syntax no highlighting for invalid targets
- [ ] Agent extraction of single-line TEST_TARGETS
- [ ] Agent extraction of multi-line TEST_TARGETS

## Files to Modify

1. ✏️ `home/lib/gai/work_projects_workflow/workflow_nodes.py`
   - `_parse_project_spec` - parsing logic
   - `_format_changespec` - formatting logic
   - `_format_changespec_with_colors` - rich output
   - Add `_test_targets_to_command_args` helper
   - Update command construction sites (lines 882, 1195, 1329)

2. ✏️ `home/dot_config/nvim/syntax/gaiproject.vim`
   - Replace TEST TARGETS syntax rules (lines 48-55)
   - Add validation pattern for bazel targets

3. ✏️ `home/lib/gai/new_failing_tests_workflow/agents.py`
   - Update TEST_TARGETS extraction (lines 60-63)

4. ✏️ `home/lib/gai/new_failing_tests_workflow/prompts.py`
   - Update format documentation (lines 107-114)

5. ✏️ `home/lib/gai/create_project_workflow/prompts.py`
   - Update format documentation (around line 127)

6. ✏️ `home/lib/gai/docs/change_spec.md`
   - Update TEST TARGETS field documentation (line 11)

7. ✏️ `home/lib/gai/test/test_work_projects_workflow.py`
   - Add comprehensive test cases

8. 📝 `home/dot_config/nvim/luasnippets/gaiproject.lua` (optional)
   - Update snippets for multi-line format

## Implementation Order

1. **Core parsing/formatting** (`workflow_nodes.py`)
   - Add multi-line parsing to `_parse_project_spec`
   - Add multi-line formatting to `_format_changespec`
   - Add helper `_test_targets_to_command_args`
   - Update command construction sites

2. **Rich output** (`workflow_nodes.py`)
   - Update `_format_changespec_with_colors`

3. **Vim syntax** (`gaiproject.vim`)
   - Add validation patterns
   - Update syntax rules

4. **Tests** (`test_work_projects_workflow.py`)
   - Add all test cases
   - Run `make test` to verify

5. **Agent support** (`agents.py`, `prompts.py`)
   - Update extraction logic
   - Update prompt documentation

6. **Documentation** (`change_spec.md`)
   - Update field specification

7. **Verification**
   - Run `make fix`
   - Run `make lint`
   - Run `make test`
   - Manual testing with real gaiproject files
