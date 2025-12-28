# Plan: Rename `gai work` to `gai search` with Query Language

## Overview

Rename `gai work` to `gai search`, remove `-s`/`-p` options, and implement a boolean query language for full-text filtering.

## Requirements

1. **Rename**: `gai work` → `gai search`
2. **Remove**: `-s` (status) and `-p` (project) filter options
3. **Add**: Required positional `query` argument with query language
4. **Full text search**: Match against name, description, status, project, history, hooks, etc.
5. **Smart case sensitivity**: `"foo"` = case-insensitive (default), `c"Foo"` = case-sensitive
6. **Zero results behavior**: Stay open and allow refresh when 0 results match (don't exit)

## Query Language

```
"foobar"                        # Case-insensitive match
c"FooBar"                       # Case-sensitive match
!"draft"                        # NOT containing "draft"
"feature" AND "test"            # Contains both
"feature" OR "bugfix"           # Contains either
("a" OR "b") AND !"skip"        # Grouped expression
```

**Precedence**: `!` (tightest) → `AND` → `OR` (loosest). Parentheses override.

## Files to Create

### 1. `home/lib/gai/work/query/` (new package)

| File | Purpose |
|------|---------|
| `__init__.py` | Export `parse_query`, `evaluate_query`, `QueryParseError` |
| `types.py` | AST types: `StringMatch`, `NotExpr`, `AndExpr`, `OrExpr` |
| `tokenizer.py` | Lexer: `tokenize()`, `Token`, `TokenType`, `TokenizerError` |
| `parser.py` | Parser: `parse_query()`, `QueryParseError` |
| `evaluator.py` | Evaluator: `evaluate_query()`, `_get_searchable_text()` |

### 2. `home/lib/gai/test/test_query.py` (new)

Tests for tokenizer, parser, and evaluator.

## Files to Modify

### 1. `home/lib/gai/main.py`

**Lines 365-396 (argument parser):**
- Rename `work_parser` → `search_parser`
- Remove `-s`/`--status` and `-p`/`--project` options
- Add required positional `query` argument

**Lines 733-741 (command handler):**
- Change `args.command == "work"` → `args.command == "search"`
- Instantiate `SearchWorkflow(query=args.query, ...)`

### 2. `home/lib/gai/work/workflow/main.py`

- Rename `WorkWorkflow` → `SearchWorkflow`
- Replace `status_filters`/`project_filters` params with `query: str`
- Parse query in `__init__` for early error detection
- Add `_filter_changespecs()` method using `evaluate_query()`
- **Fix zero-results handling**: Don't exit when `len(changespecs) == 0` - show empty state and wait for refresh

### 3. `home/lib/gai/work/workflow/__init__.py`

Update export: `SearchWorkflow` (keep `WorkWorkflow` as alias for compatibility)

### 4. `home/lib/gai/work/__init__.py`

Update exports to include `SearchWorkflow`.

### 5. `home/lib/gai/work/filters.py`

Keep for `gai loop` if needed, otherwise remove. Update imports if kept.

## Searchable Fields

`_get_searchable_text(changespec)` returns combined text from:
- `name`
- `description`
- `status`
- Project basename (from `file_path`)
- `parent` (if present)
- `cl` (if present)
- `kickstart` (if present)
- History entry notes
- Hook commands

## Implementation Steps

1. Create `home/lib/gai/work/query/types.py` with AST node dataclasses
2. Create `home/lib/gai/work/query/tokenizer.py` with lexer
3. Create `home/lib/gai/work/query/parser.py` with recursive descent parser
4. Create `home/lib/gai/work/query/evaluator.py` with evaluation logic
5. Create `home/lib/gai/work/query/__init__.py` with exports
6. Create `home/lib/gai/test/test_query.py` with tests
7. Run tests on query package
8. Rename `WorkWorkflow` → `SearchWorkflow` in `work/workflow/main.py`
9. Update constructor and filtering logic
10. Fix zero-results behavior (stay open, wait for refresh)
11. Update `work/workflow/__init__.py` and `work/__init__.py` exports
12. Update `main.py` argument parser (rename, new args)
13. Update `main.py` command handler
14. Run `make fix`, `make lint`, `make test`
15. Run `chezmoi apply`
