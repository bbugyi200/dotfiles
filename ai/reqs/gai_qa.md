# GAI Work QA Requirements

## Overview

The `gai work` command should support a QA (Quality Assurance) workflow step between presubmit completion and mailing. After presubmits succeed, the CL transitions to a "Needs QA" status where the user can run a QA workflow before proceeding to mail.

---

## Requirements

### REQ-1: New Status Value

Add a new status value to the state machine:

- **"Needs QA"** - Indicates a CL has passed presubmits and is ready for QA testing

Update `status_state_machine.py`:
- [ ] Add "Needs QA" to `VALID_STATUSES`
- [ ] Add transitions in `VALID_TRANSITIONS`

### REQ-2: Status Transitions

Configure the following state transitions:

| From Status | To Status | Trigger |
|-------------|-----------|---------|
| Running Presubmits... | Needs QA | Presubmit succeeds (via periodic check) |
| Needs QA | Pre-Mailed | QA workflow completes successfully |

- [ ] Update presubmit success transition to go to "Needs QA" instead of "Pre-Mailed"
- [ ] Add transitions to `VALID_TRANSITIONS` dict

### REQ-3: "r" (run qa) Option Availability

The existing "r" (run qa) option should be gated by status:

- [ ] Short key: `r`
- [ ] Available **only when** status is "Needs QA"
- [ ] Update `get_available_workflows()` in `operations.py` to return `["qa"]` for "Needs QA" status

### REQ-4: QA Workflow Completion

When the "r" (run qa) workflow is triggered and completes:

- [ ] Transition status from "Needs QA" to "Pre-Mailed"
- [ ] Use existing QA workflow handler logic
- [ ] Unblock any child ChangeSpecs (existing `unblock_child_changespecs()` logic)

### REQ-5: Status Color

Add color for the new status in `changespec.py` `_get_status_color()`:

- [ ] "Needs QA": `#FFD700` (bright gold, similar to other "Needs X" statuses - action needed)

---

## Implementation Notes

### Files to Modify

| File | Changes |
|------|---------|
| `status_state_machine.py` | Add "Needs QA" status and transitions |
| `work/operations.py` | Gate `["qa"]` workflow to "Needs QA" status only |
| `work/changespec.py` | Add status color for "Needs QA" |
| `work/cl_status.py` | Update presubmit success transition to "Needs QA" |

### Updated State Machine Diagram

```

                      Finishing TDD
                          CL...
                            |
                              (TDD workflow completes)
                            v

                         Needs
                       Presubmits
                            |
                              (user runs presubmit)
                            v

                        Running      (presubmit fails)
                     Presubmits...  --------------+
                            |                     |
                              (presubmit succeeds)|
                            v                     |
                                                  |
                        Needs QA  <---------------+
                            |
                              (user runs QA, QA completes)
                            v

                       Pre-Mailed
                            |
                            v

                         Mailed

```

---

## Test Coverage

Tests to add in `test/test_operations.py`:

- [ ] `test_get_available_workflows_needs_qa` - Returns `["qa"]` only for "Needs QA" status
- [ ] `test_qa_status_transitions` - Valid transitions for "Needs QA" status
- [ ] `test_runqa_not_available_other_statuses` - Verify "r" (run qa) is not available for other statuses
