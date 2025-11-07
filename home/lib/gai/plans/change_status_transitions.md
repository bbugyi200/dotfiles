# ChangeSpec STATUS Field State Transition Implementation Plan

## Overview

This plan outlines the implementation required to ensure proper state transitions for the ChangeSpec STATUS field across all gai workflows.

## Current State

### STATUS Field Definition
- Defined in: `home/lib/gai/docs/change_spec.md`
- Valid statuses defined in: `home/lib/gai/hitl_review_workflow.py` (lines 16-27)

### Current STATUS Transition Handling
Status transitions are currently handled in `home/lib/gai/work_projects_workflow/workflow_nodes.py`:
- `_update_changespec_status()` function (lines 1087-1123) performs status updates
- Status tracking in workflow state (`status_updated_to_in_progress`, `status_updated_to_fixing_tests`)
- Interrupt handling in `work_projects_workflow/main.py` (lines 109-140) reverts status on Ctrl+C

### Gaps Identified
1. **No centralized state machine**: Status transitions are scattered across workflow_nodes.py
2. **No transition validation**: No validation that transitions are valid (e.g., can't go from "Mailed" to "In Progress")
3. **Incomplete interrupt handling**: Only some status changes are tracked for rollback
4. **Missing transitions**: Not all required transitions have corresponding workflow code

## Required State Transitions

### Workflow-Driven Transitions

| From | To | Trigger | Current Implementation |
|------|-----|---------|------------------------|
| "Not Started" | "In Progress" | new-failed-tests workflow starts | ✅ Implemented (lines 1333-1338) |
| "In Progress" | "Not Started" | new-failed-tests fails or Ctrl+C | ⚠️ Partial (Ctrl+C handling exists) |
| "In Progress" | "TDD CL Created" | new-failed-tests creates TDD CL | ✅ Implemented (lines 599-651) |
| "TDD CL Created" | "Fixing Tests" | fix-tests workflow starts | ✅ Implemented (lines 678-684) |
| "Fixing Tests" | "TDD CL Created" | fix-tests workflow fails | ❌ Missing (currently goes to "Failed to Fix Tests") |
| "Fixing Tests" | "Pre-Mailed" | fix-tests workflow succeeds | ✅ Implemented (lines 759-767) |

### Manual Transitions

| From | To | Trigger | Current Implementation |
|------|-----|---------|------------------------|
| "Pre-Mailed" | "Mailed" | User confirms to mail CL | ❌ Manual only |
| "Mailed" | "Submitted" | CL is submitted | ❌ Manual only |

## Implementation Strategy

### Phase 1: Create State Machine Module

Create `home/lib/gai/status_state_machine.py` with:

1. **Status enum/constants**: Define all valid statuses
2. **Transition validation function**: `is_valid_transition(from_status: str, to_status: str) -> bool`
3. **Transition map**: Dictionary defining all valid transitions
4. **Transition trigger function**: `transition_status(project_file, changespec_name, from_status, to_status, reason) -> bool`

Benefits:
- Centralized transition logic
- Easy to add new transitions
- Validation prevents invalid state changes
- Better logging and debugging

### Phase 2: Update Workflow Integration

#### 2.1 new-failed-tests Workflow

File: `home/lib/gai/new_failing_tests_workflow/workflow_nodes.py`

Changes:
1. **Workflow start**: Transition "Not Started" → "In Progress"
   - Location: After validation (line 179)
   - Track transition for rollback

2. **CL creation success**: Transition "In Progress" → "TDD CL Created"
   - Location: After CL is created successfully
   - Current implementation in work_projects_workflow needs to be moved here

3. **Workflow failure**: Transition "In Progress" → "Not Started"
   - Location: Error handlers
   - Track which transitions need rollback

4. **Ctrl+C handling**: Transition "In Progress" → "Not Started"
   - Location: Interrupt handler
   - Use existing state tracking pattern from work_projects_workflow

#### 2.2 fix-tests Workflow

File: `home/lib/gai/fix_tests_workflow/workflow_nodes.py`

Changes:
1. **Workflow start**: Transition "TDD CL Created" → "Fixing Tests"
   - Location: Workflow entry point
   - Track transition for rollback

2. **Fix success**: Transition "Fixing Tests" → "Pre-Mailed"
   - Location: After tests are fixed successfully
   - Current implementation in work_projects_workflow needs to be moved here

3. **Fix failure**: Transition "Fixing Tests" → "TDD CL Created" (NOT "Failed to Fix Tests")
   - Location: Error handlers
   - **IMPORTANT**: This differs from current implementation
   - Allows retry without manual intervention

4. **Ctrl+C handling**: Transition "Fixing Tests" → "TDD CL Created"
   - Location: Interrupt handler
   - Use state tracking pattern

#### 2.3 work-projects Workflow

File: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

Changes:
1. Update all `_update_changespec_status()` calls to use new state machine
2. Add validation before each transition
3. Improve error messages when transitions are invalid
4. Ensure Ctrl+C handler uses state machine for rollbacks

### Phase 3: State Tracking for Rollback

Enhance state tracking in each workflow:

1. **Track transition history**: Store list of (from_status, to_status, timestamp) tuples
2. **Rollback on interrupt**: Revert to previous status on Ctrl+C
3. **Rollback on error**: Conditionally revert on workflow failures

Pattern:
```python
class WorkflowState:
    status_transitions: list[tuple[str, str, datetime]] = []

    def track_transition(self, from_status: str, to_status: str):
        self.status_transitions.append((from_status, to_status, datetime.now()))

    def get_last_status(self) -> str | None:
        if self.status_transitions:
            return self.status_transitions[-1][0]
        return None
```

### Phase 4: Manual Transition Support

Create utility script: `home/lib/gai/scripts/update_changespec_status.py`

Purpose:
- Allow manual status transitions (e.g., "Pre-Mailed" → "Mailed")
- Validate transition is allowed
- Update ChangeSpec STATUS field
- Log transition with timestamp and reason

Usage:
```bash
update-changespec-status <project-file> <changespec-name> <new-status> [--reason <reason>]
```

Validation:
- Check current status
- Validate transition is allowed (using state machine)
- Require confirmation for destructive transitions
- Support force flag for emergency overrides

### Phase 5: Testing

1. **Unit tests**: Test state machine transition validation
2. **Integration tests**: Test each workflow's status transitions
3. **Interrupt tests**: Test Ctrl+C handling for each workflow
4. **Manual transition tests**: Test the utility script

Test files:
- `home/lib/gai/tests/test_status_state_machine.py`
- `home/lib/gai/tests/test_workflow_status_transitions.py`

## Implementation Details

### State Transition Map

```python
# home/lib/gai/status_state_machine.py

VALID_TRANSITIONS = {
    "Not Started": ["In Progress"],
    "In Progress": ["Not Started", "TDD CL Created", "Failed to Create CL"],
    "TDD CL Created": ["Fixing Tests"],
    "Fixing Tests": ["TDD CL Created", "Pre-Mailed", "Failed to Fix Tests"],
    "Pre-Mailed": ["Mailed"],
    "Mailed": ["Submitted"],
    # Failed states are terminal (require manual intervention to restart)
    "Failed to Create CL": ["Not Started"],
    "Failed to Fix Tests": ["TDD CL Created"],
    "Submitted": [],  # Terminal state
}
```

Note: The transition "Fixing Tests" → "Failed to Fix Tests" is included for completeness, but per requirements, workflow code should transition to "TDD CL Created" instead to allow automatic retry.

### Status Update Function Enhancement

Current: `_update_changespec_status(project_file, changespec_name, new_status)`

Enhanced: `transition_changespec_status(project_file, changespec_name, new_status, validate=True)`

Changes:
1. Read current status before updating
2. Validate transition if `validate=True`
3. Log transition with timestamp
4. Return `(success: bool, old_status: str, error_msg: str | None)`

### Interrupt Handling Pattern

Each workflow should implement:

1. **State tracking**: Store transitions in workflow state
2. **Signal handler**: Catch SIGINT (Ctrl+C)
3. **Rollback logic**: Revert last transition
4. **Cleanup**: Ensure consistent state before exit

Example (in workflow main.py):
```python
try:
    # Run workflow
    result = workflow.run()
except KeyboardInterrupt:
    logger.warning("Workflow interrupted by user")
    if state.status_transitions:
        last_from, last_to, _ = state.status_transitions[-1]
        transition_changespec_status(
            project_file,
            changespec_name,
            last_from,  # Revert to previous status
            validate=False  # Skip validation for rollback
        )
    raise
```

## Migration Path

### Step 1: Create state machine module (no behavior change)
- Implement status_state_machine.py
- Add tests
- Validate against current transitions

### Step 2: Update work-projects workflow (preserve current behavior)
- Replace direct `_update_changespec_status()` calls
- Add validation (but don't enforce yet)
- Log any invalid transitions that would occur

### Step 3: Update new-failed-tests workflow
- Add status tracking to workflow state
- Implement transition on workflow start
- Implement rollback on error/interrupt
- Change "Fixing Tests" → "TDD CL Created" transition (instead of "Failed to Fix Tests")

### Step 4: Update fix-tests workflow
- Add status tracking to workflow state
- Implement transition on workflow start
- Implement rollback on error/interrupt
- Change failure transition to "TDD CL Created"

### Step 5: Enable strict validation
- Enforce transition validation
- Fail fast on invalid transitions
- Update any workflows that violate constraints

### Step 6: Add manual transition tool
- Create update-changespec-status script
- Add to PATH
- Document usage

## Specific Code Changes

### 1. new-failed-tests Workflow Status Changes

**File**: `home/lib/gai/new_failing_tests_workflow/workflow_nodes.py`

**Change 1: Add transition on workflow start**
```python
# After line 179 (after status validation)
# Transition "Not Started" → "In Progress"
from gai.status_state_machine import transition_changespec_status

old_status = changespec["STATUS"]
success, _, error = transition_changespec_status(
    state.project_file,
    state.changespec_name,
    "In Progress",
    validate=True
)
if not success:
    raise ValueError(f"Failed to transition status: {error}")
state.track_status_transition(old_status, "In Progress")
```

**Change 2: Add state tracking to state.py**
```python
# home/lib/gai/new_failing_tests_workflow/state.py
status_transitions: list[tuple[str, str]] = field(default_factory=list)

def track_status_transition(self, from_status: str, to_status: str):
    self.status_transitions.append((from_status, to_status))
```

**Change 3: Add interrupt handling to main.py**
```python
# home/lib/gai/new_failing_tests_workflow/main.py
try:
    result = workflow.run()
except KeyboardInterrupt:
    if state.status_transitions:
        last_from, _ = state.status_transitions[-1]
        transition_changespec_status(
            state.project_file,
            state.changespec_name,
            last_from,
            validate=False
        )
    raise
```

### 2. fix-tests Workflow Status Changes

**File**: `home/lib/gai/fix_tests_workflow/workflow_nodes.py`

**Change 1: Add transition on workflow start**
Similar pattern to new-failed-tests workflow

**Change 2: Change failure transition**
Currently: "Fixing Tests" → "Failed to Fix Tests"
New: "Fixing Tests" → "TDD CL Created"

This allows automatic retry without manual intervention.

### 3. work-projects Workflow Updates

**File**: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

Replace all `_update_changespec_status()` calls with `transition_changespec_status()` and add validation.

## Edge Cases

### 1. Manual STATUS changes
If user manually edits project file, validation may fail on next workflow run.
Solution: Allow force flag to override validation when needed.

### 2. Multiple ChangeSpecs in flight
If multiple ChangeSpecs are being worked on simultaneously, ensure transitions don't conflict.
Solution: Transitions are per-ChangeSpec, so this should work naturally.

### 3. Failed states
"Failed to Create CL" and "Failed to Fix Tests" should allow transition back to retry.
Solution: Include these in transition map.

### 4. Workflow interrupted mid-transition
If process is killed during status update, file may be in inconsistent state.
Solution: Make status updates atomic (write to temp file, then rename).

## Success Criteria

1. ✅ All required transitions are implemented
2. ✅ Invalid transitions are prevented
3. ✅ Ctrl+C handling works for all workflows
4. ✅ Workflow failures trigger correct status transitions
5. ✅ Manual transition tool works correctly
6. ✅ All tests pass
7. ✅ No regression in existing workflow behavior
8. ✅ Status transitions are logged for debugging

## Follow-up Enhancements

1. **Transition history**: Store full transition history in ChangeSpec (new field)
2. **Transition timestamps**: Track when each transition occurred
3. **Transition reasons**: Require reason for manual transitions
4. **State machine visualization**: Generate diagram of valid transitions
5. **Metrics**: Track time spent in each state
6. **Notifications**: Alert when ChangeSpec has been in a state too long
