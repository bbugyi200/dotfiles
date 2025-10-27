import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from shared_utils import run_shell_command

from .prompts import (
    build_context_prompt,
    build_editor_prompt,
    build_judge_prompt,
    build_verification_prompt,
)
from .state import FixTestsState


def check_for_duplicate_todos(artifacts_dir: str, current_iteration: int) -> bool:
    """Check if the current editor_todos.md is similar to previous iterations."""
    current_todos_path = os.path.join(artifacts_dir, "editor_todos.md")

    if not os.path.exists(current_todos_path):
        return False

    try:
        with open(current_todos_path, "r") as f:
            current_content = f.read().strip()
    except Exception:
        return False

    # Check against previous iterations' todo files
    for iter_num in range(1, current_iteration):
        prev_todos_path = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_todos.txt"
        )
        if os.path.exists(prev_todos_path):
            try:
                with open(prev_todos_path, "r") as f:
                    prev_content = f.read().strip()

                # Simple similarity check - if 80% of lines are identical, consider it duplicate
                current_lines = set(current_content.lower().split("\n"))
                prev_lines = set(prev_content.lower().split("\n"))

                if current_lines and prev_lines:
                    intersection = current_lines.intersection(prev_lines)
                    similarity = len(intersection) / max(
                        len(current_lines), len(prev_lines)
                    )

                    if similarity > 0.8:
                        print(
                            f"High similarity ({similarity:.2f}) detected with iteration {iter_num}"
                        )
                        return True

            except Exception:
                continue

    return False


def create_agent_changes_diff(artifacts_dir: str, iteration: int) -> None:
    """Create a diff file showing changes made by the current agent iteration."""
    try:
        # Get the current diff from the working directory
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
    iteration = state["current_iteration"]
    print(f"Running editor agent (iteration {iteration})...")

    # Check if editor_todos.md exists
    artifacts_dir = state["artifacts_dir"]
    todos_path = os.path.join(artifacts_dir, "editor_todos.md")

    if not os.path.exists(todos_path):
        print(
            "⚠️ Warning: editor_todos.md not found - editor agent may not have proper guidance"
        )

    # Build prompt for editor
    prompt = build_editor_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Editor agent response received")

    # Save the agent's response with iteration-specific name (for context agent only)
    response_path = os.path.join(
        state["artifacts_dir"], f"editor_iter_{iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Also save as agent_reply.md for current iteration processing by context agent
    agent_reply_path = os.path.join(state["artifacts_dir"], "agent_reply.md")
    with open(agent_reply_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"EDITOR AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Check if todos were completed (look for DONE markers or similar)
    if os.path.exists(todos_path):
        try:
            with open(todos_path, "r") as f:
                todos_content = f.read()

            # Count total todos and completed todos
            total_todos = (
                todos_content.count("- [ ]")
                + todos_content.count("- [x]")
                + todos_content.count("- [X]")
            )
            completed_todos = todos_content.count("- [x]") + todos_content.count(
                "- [X]"
            )

            if total_todos > 0:
                completion_rate = completed_todos / total_todos
                print(
                    f"📋 Todo completion: {completed_todos}/{total_todos} ({completion_rate:.1%})"
                )

                if completion_rate < 1.0:
                    print("⚠️ Warning: Not all todos were completed by the editor agent")
            else:
                print("📋 No checkbox todos found in editor_todos.md")

        except Exception as e:
            print(f"⚠️ Warning: Could not check todo completion: {e}")

    # Create a diff of changes made by this agent for the judge to review
    create_agent_changes_diff(state["artifacts_dir"], iteration)

    return {**state, "messages": state["messages"] + messages + [response]}


def run_test(state: FixTestsState) -> FixTestsState:
    """Run the actual test command and check if it passes."""
    iteration = state["current_iteration"]
    test_cmd = state["test_cmd"]
    print(f"Running test command (iteration {iteration}): {test_cmd}")

    artifacts_dir = state["artifacts_dir"]

    # Run the actual test command
    print(f"Executing: {test_cmd}")
    result = run_shell_command(test_cmd, capture_output=True)

    # Check if test passed
    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Test PASSED!")
    else:
        print("❌ Test failed")

    # Print test output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Test stderr: {result.stderr}")

    # Save iteration-specific full test output for context agent review
    test_output_content = f"Command: {test_cmd}\nReturn code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n"
    iter_test_output_path = os.path.join(
        artifacts_dir, f"editor_iter_{iteration}_test_output.txt"
    )
    with open(iter_test_output_path, "w") as f:
        f.write(test_output_content)

    # Copy editor_todos.md to iteration-specific file for archival and agent coordination
    editor_todos_path = os.path.join(artifacts_dir, "editor_todos.md")
    if os.path.exists(editor_todos_path):
        iter_todos_path = os.path.join(
            artifacts_dir, f"editor_iter_{iteration}_todos.txt"
        )
        try:
            import shutil

            shutil.copy2(editor_todos_path, iter_todos_path)
            print(f"✅ Copied editor todos to {iter_todos_path}")
        except Exception as e:
            print(f"⚠️ Warning: Failed to copy editor todos: {e}")

    # Note: User instructions file is never modified or deleted - it remains at its original path

    return {**state, "test_passed": test_passed}


def apply_agent_changes(artifacts_dir: str, selected_agent: int, test_cmd: str) -> bool:
    """Apply the selected agent's changes to the codebase."""
    try:
        # Find the changes diff file for the selected agent
        changes_file = os.path.join(
            artifacts_dir, f"editor_iter_{selected_agent}_changes.diff"
        )

        if not os.path.exists(changes_file):
            print(f"Error: Changes file not found: {changes_file}")
            return False

        # Apply the patch
        apply_cmd = f"hg import --no-commit {changes_file}"
        result = run_shell_command(apply_cmd, capture_output=True)

        if result.returncode != 0:
            print(f"Error applying patch: {result.stderr}")
            return False

        print(f"✅ Successfully applied changes from agent {selected_agent}")

        # Create a short description of the changes
        with open(changes_file, "r") as f:
            diff_content = f.read()

        # Extract file names from diff for description
        import re

        file_matches = re.findall(r"\+\+\+ b/(.+)", diff_content)
        if file_matches:
            files_changed = ", ".join(file_matches[:3])  # First 3 files
            if len(file_matches) > 3:
                files_changed += f" and {len(file_matches) - 3} more"
            desc = f"Applied agent {selected_agent} changes to {files_changed}"
        else:
            desc = f"Applied agent {selected_agent} changes"

        # Amend the commit
        amend_cmd = f'hg amend -n "@AI #fix-tests {desc}"'
        result = run_shell_command(amend_cmd, capture_output=True)

        if result.returncode != 0:
            print(f"Warning: Failed to amend commit: {result.stderr}")
            # Don't fail the whole operation for this
        else:
            print(f"✅ Amended commit with description: {desc}")

        return True

    except Exception as e:
        print(f"Error applying agent changes: {e}")
        return False


def get_new_test_output_file(artifacts_dir: str, selected_agent: int) -> str:
    """Get the test output file from the selected agent for workflow restart."""
    test_output_file = os.path.join(
        artifacts_dir, f"editor_iter_{selected_agent}_test_output.txt"
    )
    if os.path.exists(test_output_file):
        return test_output_file
    else:
        # Fallback to original test output
        return os.path.join(artifacts_dir, "test_output.txt")


def get_user_confirmation(artifacts_dir: str, selected_agent: int) -> bool:
    """Show the user the judge's selection and get confirmation to proceed."""
    print("\n" + "=" * 80)
    print("🤖 JUDGE AGENT SELECTION - HUMAN CONFIRMATION REQUIRED")
    print("=" * 80)

    # Show which agent was selected
    print(f"📋 Judge selected: Agent Iteration {selected_agent}")
    print()

    # Show the agent's response/analysis
    response_file = os.path.join(
        artifacts_dir, f"editor_iter_{selected_agent}_response.txt"
    )
    if os.path.exists(response_file):
        print("📝 SELECTED AGENT'S ANALYSIS:")
        print("-" * 40)
        try:
            with open(response_file, "r") as f:
                content = f.read().strip()
                # Show full content without truncation
                print(content)
        except Exception as e:
            print(f"Error reading agent response: {e}")
        print()

    # Show the changes that will be applied
    changes_file = os.path.join(
        artifacts_dir, f"editor_iter_{selected_agent}_changes.diff"
    )
    if os.path.exists(changes_file):
        print("🔧 CHANGES TO BE APPLIED:")
        print("-" * 40)
        try:
            with open(changes_file, "r") as f:
                diff_content = f.read().strip()
                if diff_content:
                    # Show full diff content without truncation
                    print(diff_content)
                else:
                    print("No changes detected in diff file.")
        except Exception as e:
            print(f"Error reading changes diff: {e}")
        print()
    else:
        print("⚠️ Warning: No changes diff file found!")
        print()

    # Show the test failure that will be used for restart
    test_output_file = os.path.join(
        artifacts_dir, f"editor_iter_{selected_agent}_test_output.txt"
    )
    if os.path.exists(test_output_file):
        print("🧪 TEST FAILURE OUTPUT:")
        print("-" * 40)
        try:
            with open(test_output_file, "r") as f:
                test_content = f.read().strip()
                # Show full test output without truncation
                print(test_content)
        except Exception as e:
            print(f"Error reading test output: {e}")
        print()

    print("=" * 80)
    print("❓ DECISION REQUIRED:")
    print("   ✅ Apply these changes and restart fix-tests workflow")
    print("   ❌ Abort the workflow (no changes will be applied)")
    print("=" * 80)

    # Get user input
    while True:
        try:
            response = (
                input("Do you want to apply these changes? [y/n]: ").strip().lower()
            )
            if response in ["y", "yes"]:
                print("✅ User confirmed - applying changes...")
                return True
            elif response in ["n", "no"]:
                print("❌ User declined - aborting workflow...")
                return False
            else:
                print("Please enter 'y' or 'n'")
        except (EOFError, KeyboardInterrupt):
            print("\n❌ User interrupted - aborting workflow...")
            return False


def run_judge_agent(state: FixTestsState) -> FixTestsState:
    """Run the judge agent to select the best changes from all iterations."""
    artifacts_dir = state["artifacts_dir"]
    judge_iteration = state["current_judge_iteration"]
    print(f"Running judge agent (judge iteration {judge_iteration})...")

    # Build judge prompt
    prompt = build_judge_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Judge agent response received")

    # Save the judge's response
    response_path = os.path.join(
        artifacts_dir, f"judge_iter_{judge_iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"JUDGE AGENT RESPONSE (JUDGE ITERATION {judge_iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Parse the judge's selection (expecting format like "SELECTED AGENT: 3")
    selected_agent = None
    lines = response.content.split("\n")
    for line in lines:
        if line.startswith("SELECTED AGENT:"):
            try:
                selected_agent = int(line.split(":")[1].strip())
                break
            except (ValueError, IndexError):
                continue

    if selected_agent is None:
        return {
            **state,
            "test_passed": False,
            "failure_reason": "Judge agent failed to select an agent",
            "messages": state["messages"] + messages + [response],
        }

    print(f"Judge selected agent iteration {selected_agent}")

    # Get user confirmation before applying changes (unless no_human_approval is set)
    if state.get("no_human_approval", False):
        print("Skipping human approval (--no-human-approval flag set)")
        user_approved = True
    else:
        user_approved = get_user_confirmation(artifacts_dir, selected_agent)

    if not user_approved:
        return {
            **state,
            "test_passed": False,
            "failure_reason": "User declined to apply judge's selected changes",
            "messages": state["messages"] + messages + [response],
        }

    # Apply the selected agent's changes
    success = apply_agent_changes(artifacts_dir, selected_agent, state["test_cmd"])

    if not success:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Failed to apply changes from agent {selected_agent}",
            "messages": state["messages"] + messages + [response],
        }

    # Get new test output file for restart
    new_test_output_file = get_new_test_output_file(artifacts_dir, selected_agent)

    return {
        **state,
        "test_output_file": new_test_output_file,
        "current_iteration": 1,  # Reset for new workflow run
        "current_judge_iteration": judge_iteration + 1,
        "judge_applied_changes": state["judge_applied_changes"] + 1,
        "artifacts_dir": "",  # Will be reset by new workflow
        "requirements_exists": False,
        "research_exists": False,
        "context_agent_retries": 0,
        "messages": state["messages"] + messages + [response],
    }


def run_verification_agent(state: FixTestsState) -> FixTestsState:
    """Run the verification agent to check if editor changes match todos and have no syntax errors."""
    iteration = state["current_iteration"]
    verification_retry = state.get("verification_retries", 0)
    print(
        f"Running verification agent (iteration {iteration}, verification retry {verification_retry})..."
    )

    # Build prompt for verification
    prompt = build_verification_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Verification agent response received")

    # Save the verification agent's response
    response_path = os.path.join(
        state["artifacts_dir"],
        f"verification_iter_{iteration}_retry_{verification_retry}_response.txt",
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(
        f"VERIFICATION AGENT RESPONSE (ITERATION {iteration}, RETRY {verification_retry}):"
    )
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Parse the verification result (expecting format like "VERIFICATION: PASS" or "VERIFICATION: FAIL")
    verification_passed = False
    needs_editor_retry = False
    lines = response.content.split("\n")

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
            break

    if not verification_passed and not needs_editor_retry:
        # If we couldn't parse the result, assume failure
        needs_editor_retry = True
        print("⚠️ Could not parse verification result - assuming failure")

    return {
        **state,
        "verification_passed": verification_passed,
        "needs_editor_retry": needs_editor_retry,
        "messages": state["messages"] + messages + [response],
    }


def run_context_agent(state: FixTestsState) -> FixTestsState:
    """Run the context/research agent to create editor todos and update research log."""
    iteration = state["current_iteration"]
    print(f"Running research agent (iteration {iteration})...")

    # Build prompt for context agent
    prompt = build_context_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Research agent response received")

    # Print the response
    print("\n" + "=" * 80)
    print(f"RESEARCH AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Research agent must always create editor_todos.md

    # Check if editor_todos.md file was actually created
    artifacts_dir = state["artifacts_dir"]
    editor_todos_path = os.path.join(artifacts_dir, "editor_todos.md")

    todos_created = os.path.exists(editor_todos_path)

    # Check if research.md was updated
    research_path = os.path.join(artifacts_dir, "research.md")
    research_updated = os.path.exists(research_path)

    files_updated = todos_created

    if not files_updated:
        # Agent didn't create todo file
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(
                f"Research agent failed to create editor_todos.md after {retries} retries - workflow will abort"
            )
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Research agent failed to create editor_todos.md after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Research agent didn't create editor_todos.md, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }

    print("✅ Editor todos created successfully")
    if research_updated:
        print("✅ Research log updated successfully")

    # Check for duplicate todo lists by comparing with previous iterations
    duplicate_detected = check_for_duplicate_todos(artifacts_dir, iteration)
    if duplicate_detected:
        print(
            "⚠️ Warning: Duplicate todo list detected - research agent should create a different approach"
        )
        # We could retry here, but let's proceed for now and let the workflow handle it

    # Automatically stash local changes to give the next editor agent a fresh start
    print("Stashing local changes for next editor agent...")
    stash_result = run_shell_command("stash_local_changes", capture_output=True)
    if stash_result.returncode == 0:
        print("✅ Local changes stashed successfully")
    else:
        print(f"⚠️ Warning: Failed to stash local changes: {stash_result.stderr}")

    return {
        **state,
        "todos_created": todos_created,
        "research_updated": research_updated,
        "context_agent_retries": 0,  # Reset retries on success
        "current_iteration": state["current_iteration"]
        + 1,  # Increment iteration for next cycle
        "messages": state["messages"] + messages + [response],
    }
