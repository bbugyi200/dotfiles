import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    ensure_str_content,
    run_shell_command,
)

from ..prompts import (
    build_editor_prompt,
)
from ..state import (
    FixTestsState,
)


def revert_rejected_changes(
    artifacts_dir: str, iteration: int, verification_retry: int
) -> None:
    """Revert local changes that were rejected by verification agent."""
    try:
        result = run_shell_command("hg update --clean .", capture_output=True)
        if result.returncode == 0:
            print("✅ Reverted rejected changes for fresh editor retry")
        else:
            print(f"⚠️ Warning: Failed to stash local changes: {result.stderr}")
    except Exception as e:
        print(f"⚠️ Warning: Error stashing rejected changes: {e}")


def clear_completed_todos(artifacts_dir: str) -> None:
    """DEPRECATED: No longer needed since file modifications are passed directly in prompts."""
    pass


def _create_agent_changes_diff(artifacts_dir: str, iteration: int) -> None:
    """Create a diff file showing changes made by the current agent iteration."""
    try:
        diff_cmd = "hg diff"
        result = run_shell_command(diff_cmd, capture_output=True)
        if result.returncode == 0:
            diff_file_path = os.path.join(
                artifacts_dir, f"editor_iter_{iteration}_changes.diff"
            )
            with open(diff_file_path, "w") as f:
                f.write(result.stdout)
            print(f"✅ Created changes diff: {diff_file_path}")
        else:
            print(f"⚠️ Warning: Failed to create diff: {result.stderr}")
    except Exception as e:
        print(f"⚠️ Warning: Error creating agent changes diff: {e}")


def run_editor_agent(state: FixTestsState) -> FixTestsState:
    """Run the editor/fixer agent to attempt fixing the test."""
    editor_iteration = state["current_iteration"] - 1
    print_status(
        f"Running editor agent (editor iteration {editor_iteration})...", "progress"
    )
    prompt = build_editor_prompt(state)
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="editor",
        iteration=editor_iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status("Editor agent response received", "success")
    response_text = ensure_str_content(response.content)
    response_path = os.path.join(
        state["artifacts_dir"], f"editor_iter_{editor_iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response_text)
    agent_reply_path = os.path.join(state["artifacts_dir"], "agent_reply.md")
    with open(agent_reply_path, "w") as f:
        f.write(response_text)
    _create_agent_changes_diff(state["artifacts_dir"], editor_iteration)
    return {**state, "messages": state["messages"] + messages + [response]}
