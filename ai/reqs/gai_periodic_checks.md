# GAI Work Periodic Checks Requirements

## Overview

The `gai work` command should periodically check mailed ChangeSpecs for status updates (submission, comments) and automatically update their status when appropriate.

---

## Implemented Requirements

### REQ-1: Submission Status Checking
- [x] Check if mailed CLs have been submitted using `is_cl_submitted <name>` command
- [x] Update status from "Mailed" to "Submitted" when CL is submitted

### REQ-2: Time-Based Throttling
- [x] Each ChangeSpec is checked at most once every 5 minutes
- [x] Track last_checked timestamps in `~/.gai/sync_cache.json`

### REQ-3: Parent Dependency Check
- [x] Only check a ChangeSpec if it has no parent OR its parent's status is "Submitted"
- [x] Skip checking if parent exists and is not yet submitted

### REQ-4: Workspace Directory
- [x] Run `is_cl_submitted` and `critique_comment` from the correct workspace directory (`$GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE`)

### REQ-5: User Feedback
- [x] Pretty-print status messages when syncing CLs:
  - Cyan: "Syncing '<name>'..."
  - Green: Success message when CL submitted
  - Yellow: Message when comments detected
  - Dim: Message when CL is up to date

### REQ-6: Manual Sync Option
- [x] "y" (sync all) option to manually trigger sync for ALL eligible ChangeSpecs
- [x] Force bypasses the 5-minute throttle

### REQ-7: Triggers
- [x] Check on startup for ALL mailed/changes-requested CLs across all projects
- [x] Check when navigating via "n" (next) or "p" (prev)

### REQ-8: Expanded Trigger Scope
- [x] On startup: Check ALL mailed CLs across ALL projects (not just filtered ones)
- [x] On navigation (n/p): Check ALL eligible mailed CLs (not just the target)

### REQ-9: Comment Checking
- [x] Check for reviewer comments using `critique_comment <name>` command
- [x] If command produces output, comments exist that need response
- [x] Same triggers and throttling as submission checking (5 min, parent check)

### REQ-10: "Changes Requested" Status
- [x] Add new status: "Changes Requested"
- [x] Transition from "Mailed" to "Changes Requested" when comments are detected
- [x] Update status state machine with valid transitions for this status
- [x] "Changes Requested" can transition to "Mailed" (after addressing) or "Submitted"

### REQ-11: Sync All ChangeSpecs
- [x] Change "y" option to sync ALL matched ChangeSpecs (not just current one)
- [x] Matched = mailed/changes-requested + (no parent OR parent submitted)

### REQ-12: Refresh ChangeSpec List After Sync
- [x] After any sync operation that updates statuses, refresh the ChangeSpec list
- [x] Ensure the workflow is iterating over the updated list

### REQ-13: Auto-Transition from "Changes Requested" to "Mailed"
- [x] Check if ChangeSpecs with "Changes Requested" status have no pending comments
- [x] If `critique_comments <name>` produces no output, transition back to "Mailed"
- [x] Same triggers and throttling as other checks (5 min, startup/navigation triggers)

---

## Implementation Notes

### Files Involved
- `home/lib/gai/work/cl_status.py` - CL submission/comment checking logic
- `home/lib/gai/work/sync_cache.py` - Timestamp caching for throttling
- `home/lib/gai/work/workflow.py` - Main workflow with navigation and sync options
- `home/lib/gai/status_state_machine.py` - Status transitions
- `home/lib/gai/work/changespec.py` - Color for "Changes Requested" status
- `home/bin/executable_is_cl_submitted` - Shell script to check submission status

### Syncable Statuses
Both "Mailed" and "Changes Requested" statuses are checked for:
1. Submission status (-> "Submitted")
2. Pending comments (only for "Mailed" -> "Changes Requested")
