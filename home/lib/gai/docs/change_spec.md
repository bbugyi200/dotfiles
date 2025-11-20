# ChangeSpec Format Documentation

A **ChangeSpec** is a structured specification for a change list (CL), also known as a pull request (PR). It defines the metadata, description, dependencies, and status of a proposed code change.

## Format Overview

Each ChangeSpec follows this exact format:

```
NAME: <NAME>
DESCRIPTION:
  <TITLE>

  <BODY>
PARENT: <PARENT>
CL: <CL>
TEST TARGETS: <TEST_TARGETS>
STATUS: <STATUS>
```

**IMPORTANT**: When outputting multiple ChangeSpecs, separate each one with **two blank lines**.

## Field Specifications

### NAME

The unique identifier for the change list.

**Format**: `<prefix>_<descriptive_suffix>`
- Must start with a project-specific prefix followed by an underscore
- Suffix should use underscores to separate words
- Suffix should be descriptive but concise

**Examples**:
- `my_project_add_config_parser`
- `feature_x_implement_validation`
- `refactor_database_layer`

### DESCRIPTION

A comprehensive description of what the CL does and why.

**Structure**:
1. **TITLE** (first line): A brief one-line summary
2. **Blank line**: Always include one blank line after the title
3. **BODY** (remaining lines): Detailed multi-line description

**Formatting**:
- **All lines must be 2-space indented** (including the blank line)
- TITLE should be concise (one line)
- BODY should include:
  - What changes are being made
  - Why the changes are needed
  - High-level approach or implementation details
  - What will be tested (if applicable)

**Example**:
```
DESCRIPTION:
  Add configuration file parser for user settings

  This CL implements a YAML-based configuration parser that reads
  user settings from ~/.myapp/config.yaml. The parser includes a
  ConfigParser class with load() and validate() methods, along with
  type definitions for the configuration schema. Tests will cover
  valid YAML parsing, invalid config validation, and missing file
  handling.
```

### PARENT

Specifies the dependency relationship between CLs.

**Values**:
- `None` - This CL has no dependencies (default, preferred for parallelization)
- `<parent_cl_name>` - The NAME of a parent CL that must be completed first

**CRITICAL Dependency Guidelines**:
- **Default to `None`** to maximize parallel development
- **Only set a PARENT when there's a real content dependency**:
  - CL B calls a function/class that CL A creates
  - CL B modifies a file that CL A creates
  - CL B extends functionality that CL A introduces
- **DO NOT set a PARENT for**:
  - Independent features that don't interact
  - Changes to different files/modules
  - Tests for independent features
  - Documentation that doesn't reference new code

**Examples**:
```
PARENT: None                           # No dependencies (preferred)
PARENT: my_project_add_config_parser   # Depends on another CL
```

### CL

The CL identifier (e.g., CL number or PR number).

**Values**:
- `None` - CL not yet created (initial state)
- `http://cl/<CL_ID>` - URL to the created CL/PR

**Example**:
```
CL: None                    # Before CL creation
CL: http://cl/12345        # After CL creation
```

### TEST TARGETS

Specifies the test targets that need to pass for this CL.

**This field has three possible states**:

1. **Omitted entirely**: For CLs that don't require tests
   - Config-only changes
   - SQL data changes
   - Documentation-only changes
   - New enum values
   - Small changes where tests aren't justified

2. **Specified with targets**: For CLs that require specific tests
   - Single-line format: `TEST TARGETS: //path/to:test`
   - Multi-line format (preferred for multiple targets):
     ```
     TEST TARGETS:
       //path/to:test1
       //path/to:test2
     ```
   - Each target must be 2-space indented in multi-line format
   - No blank lines between targets

3. **Field present but no value specified**: Tests are required but targets are TBD
   - Format: `TEST TARGETS:` (with nothing after the colon)

**NEVER use `TEST TARGETS: None`** - either specify targets or omit the field.

**Target Format**:
- General: `//path/to/package:target_name`
- For Dart: Strip the `test/` directory from the path
  - File: `//path/to/component/test/my_widget_test.dart`
  - Target: `//path/to/component:my_widget_test` (not `//path/to/component/test:my_widget_test`)

**Examples**:
```
# Single target
TEST TARGETS: //my/project:config_parser_test

# Multiple targets (single-line)
TEST TARGETS: //my/project:test1 //my/project:test2

# Multiple targets (multi-line, preferred)
TEST TARGETS:
  //my/project:integration_test
  //my/project:config_parser_test

# No tests required (omit field entirely)
NAME: my_project_update_config
DESCRIPTION:
  Update production config file
  ...
PARENT: None
CL: None
STATUS: Unstarted
```

### STATUS

The current state of the CL.

**Valid Values**:
- `Blocked` - Has a PARENT that hasn't reached "Pre-Mailed" status or beyond
- `Unstarted` - Ready to start but work hasn't begun
- `In Progress` - Work is currently ongoing
- `Failed to Create CL` - CL creation attempt failed
- `TDD CL Created` - Test-driven development CL created
- `Fixing Tests` - CL created but tests are failing
- `Failed to Fix Tests` - Unable to fix test failures
- `Pre-Mailed` - Ready for review but not yet mailed
- `Mailed` - Sent for review
- `Submitted` - Merged/submitted to the codebase

**Status Selection Rules**:
- If `PARENT: None`, typically use `Unstarted`
- If PARENT is set to another CL name, use `Blocked`
- Update status as work progresses through the lifecycle

## Complete Examples

### Example 1: Independent CL with Tests

```
NAME: auth_system_add_jwt_validator
DESCRIPTION:
  Add JWT token validation for authentication

  This CL implements JWT token validation using the PyJWT library.
  It includes a JWTValidator class that handles token parsing,
  signature verification, and expiration checking. The implementation
  supports both RS256 and HS256 algorithms. Tests cover valid tokens,
  expired tokens, invalid signatures, and malformed tokens.
PARENT: None
CL: None
TEST TARGETS: //auth/system:jwt_validator_test
STATUS: Unstarted
```

### Example 2: Dependent CL with Multiple Test Targets

```
NAME: auth_system_integrate_validator
DESCRIPTION:
  Integrate JWT validator into authentication middleware

  This CL integrates the JWT validator from the previous CL into
  the main authentication middleware. The middleware will validate
  tokens on protected routes and handle validation errors gracefully.
  Tests verify both successful authentication and various failure
  scenarios including missing tokens, expired tokens, and invalid
  signatures.
PARENT: auth_system_add_jwt_validator
CL: None
TEST TARGETS:
  //auth/system:middleware_test
  //auth/system:integration_test
STATUS: Blocked
```

### Example 3: Config-Only CL (No Tests)

```
NAME: auth_system_update_config
DESCRIPTION:
  Update JWT configuration with new secret key

  This CL updates the production configuration file to use a new
  secret key for JWT signing. This is a config-only change that
  rotates the signing key for security purposes.
PARENT: None
CL: None
STATUS: Unstarted
```

### Example 4: Parallel Independent CL

```
NAME: auth_system_add_rate_limiter
DESCRIPTION:
  Add rate limiting for authentication endpoints

  This CL implements rate limiting using Redis to prevent brute
  force attacks on authentication endpoints. It includes a
  RateLimiter class that tracks request counts per IP address and
  enforces configurable limits. This is completely independent of
  the JWT validation work and can be developed in parallel. Tests
  verify limit enforcement, reset behavior, and Redis failure
  handling.
PARENT: None
CL: None
TEST TARGETS: //auth/system:rate_limiter_test
STATUS: Unstarted
```

## Best Practices

1. **Keep CLs Small and Focused**: Each CL should address a single, well-defined change
2. **Maximize Parallelization**: Use `PARENT: None` whenever possible
3. **Include Tests**: Most CLs should specify TEST TARGETS
4. **Write Clear Descriptions**: Explain what, why, and how
5. **Use Descriptive Names**: NAME should clearly indicate what the CL does
6. **Think About Dependencies**: Only create dependencies when truly necessary
7. **Update Status Appropriately**: Keep STATUS field current as work progresses
