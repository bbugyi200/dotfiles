import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    ensure_str_content,
    safe_hg_amend,
)

from ..prompts import (
    build_verification_prompt,
)
from ..state import (
    FixTestsState,
)
from .editor import _clear_completed_todos, _revert_rejected_changes


def run_verification_agent(state: FixTestsState) -> FixTestsState:
    """Run the verification agent to check if editor changes match todos and have no syntax errors."""
    editor_iteration = state["current_iteration"] - 1
    verification_retry = state.get("verification_retries", 0)
    print(
        f"Running verification agent (editor iteration {editor_iteration}, verification retry {verification_retry})..."
    )
    prompt = build_verification_prompt(state)
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="verification",
        iteration=editor_iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status("Verification agent response received", "success")
    response_path = os.path.join(
        state["artifacts_dir"],
        f"verification_iter_{editor_iteration}_retry_{verification_retry}_response.txt",
    )
    with open(response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    verification_passed = False
    needs_editor_retry = False
    needs_planner_retry = False
    commit_msg = None
    verifier_note = None
    planner_retry_note = None
    amend_successful = False
    lines = ensure_str_content(response.content).split("\n")
    for line in lines:
        if line.startswith("VERIFICATION:"):
            result = line.split(":")[1].strip().upper()
            if result == "PASS":
                verification_passed = True
                print("✅ Verification PASSED - proceeding to test execution")
            elif result == "FAIL":
                verification_passed = False
                needs_editor_retry = True
                print("❌ Verification FAILED - editor agent needs to retry")
            elif result == "PLANNER_RETRY":
                verification_passed = False
                needs_editor_retry = False
                needs_planner_retry = True
                print(
                    "🔄 Verification requests PLANNER RETRY - editor correctly identified invalid plan"
                )
        elif line.startswith("COMMIT_MSG:") and verification_passed:
            commit_msg = line.split(":", 1)[1].strip()
            print(f"📝 Commit message: {commit_msg}")
        elif line.startswith("VERIFIER_NOTE:") and needs_editor_retry:
            verifier_note = line.split(":", 1)[1].strip()
            print(f"📝 Verifier note: {verifier_note}")
        elif line.startswith("PLANNER_RETRY_NOTE:") and needs_planner_retry:
            planner_retry_note = line.split(":", 1)[1].strip()
            print(f"📝 Planner retry note: {planner_retry_note}")
    if (
        not verification_passed
        and (not needs_editor_retry)
        and (not needs_planner_retry)
    ):
        needs_editor_retry = True
        print("⚠️ Could not parse verification result - assuming editor failure")
    if needs_editor_retry:
        updated_verifier_notes = state.get("verifier_notes", []).copy()
        if verifier_note:
            updated_verifier_notes.append(verifier_note)
            print(f"📝 Added verifier note to accumulated notes: {verifier_note}")
            verifier_notes_file = os.path.join(
                state["artifacts_dir"], "verifier_notes.txt"
            )
            with open(verifier_notes_file, "w") as f:
                for i, note in enumerate(updated_verifier_notes, 1):
                    f.write(f"{i}. {note}\n")
            print(
                f"📝 Saved {len(updated_verifier_notes)} verifier notes to {verifier_notes_file}"
            )
        _clear_completed_todos(state["artifacts_dir"])
        _revert_rejected_changes(
            state["artifacts_dir"], editor_iteration, verification_retry
        )
    elif needs_planner_retry:
        _revert_rejected_changes(
            state["artifacts_dir"], editor_iteration, verification_retry
        )
    elif verification_passed:
        workflow_instance = state.get("workflow_instance")
        if workflow_instance:
            workflow_instance._mark_verification_succeeded()
        is_first_verification = not state.get("first_verification_success", False)
        use_unamend_first = not is_first_verification
        print(
            f"✅ Successful verification - running {('initial' if is_first_verification else 'subsequent')} commit"
        )
        workflow_tag = state.get("workflow_tag", "XXX")
        commit_iteration = state.get("commit_iteration", 1)
        if commit_msg:
            desc_msg = commit_msg
        else:
            desc_msg = f"Editor changes iteration {editor_iteration}"
        full_commit_msg = (
            f"@AI({workflow_tag}) [fix-tests] {desc_msg} - #{commit_iteration}"
        )
        print(f"📝 Full commit message: {full_commit_msg}")
        amend_successful = safe_hg_amend(
            full_commit_msg, use_unamend_first=use_unamend_first
        )
        if not amend_successful:
            print(
                "❌ CRITICAL: hg amend failed - aborting workflow to prevent unsafe state"
            )
            return {
                **state,
                "verification_passed": False,
                "needs_editor_retry": False,
                "test_passed": False,
                "failure_reason": "hg amend failed - workflow aborted for safety",
                "last_amend_successful": False,
                "messages": state["messages"] + messages + [response],
            }
        if workflow_instance and amend_successful:
            workflow_instance._mark_amend_successful()
    new_commit_iteration = state.get("commit_iteration", 1)
    if verification_passed and amend_successful:
        new_commit_iteration += 1
    updated_verifier_notes = state.get("verifier_notes", [])
    updated_planner_retry_notes = state.get("planner_retry_notes", [])
    if verification_passed:
        updated_verifier_notes = []
        print("✅ Verification passed - cleared accumulated verifier notes")
    elif needs_editor_retry and verifier_note:
        updated_verifier_notes = updated_verifier_notes.copy()
        if verifier_note not in updated_verifier_notes:
            updated_verifier_notes.append(verifier_note)
    elif needs_planner_retry:
        updated_planner_retry_notes = updated_planner_retry_notes.copy()
        if planner_retry_note:
            updated_planner_retry_notes.append(planner_retry_note)
            print(
                f"📝 Added planner retry note to accumulated notes: {planner_retry_note}"
            )
            planner_retry_notes_file = os.path.join(
                state["artifacts_dir"], "planner_retry_notes.txt"
            )
            with open(planner_retry_notes_file, "w") as f:
                for i, note in enumerate(updated_planner_retry_notes, 1):
                    f.write(f"{i}. {note}\n")
            print(
                f"📝 Saved {len(updated_planner_retry_notes)} planner retry notes to {planner_retry_notes_file}"
            )
    return {
        **state,
        "verification_passed": verification_passed,
        "needs_editor_retry": needs_editor_retry,
        "needs_planner_retry": needs_planner_retry,
        "first_verification_success": state.get("first_verification_success", False)
        or verification_passed,
        "last_amend_successful": amend_successful,
        "safe_to_unamend": state.get("safe_to_unamend", False) or amend_successful,
        "commit_iteration": new_commit_iteration,
        "verifier_notes": updated_verifier_notes,
        "planner_retry_notes": updated_planner_retry_notes,
        "messages": state["messages"] + messages + [response],
    }
