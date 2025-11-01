import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from rich_utils import (
    create_progress_tracker,
    print_iteration_header,
    print_prompt_and_response,
    print_status,
)
from shared_utils import (
    add_iteration_section_to_log,
    add_postmortem_to_log,
    add_research_to_log,
    add_test_output_to_log,
    run_shell_command,
    run_shell_command_with_input,
    safe_hg_amend,
)

from .prompts import (
    build_context_prompt,
    build_editor_prompt,
    build_research_prompt,
    build_test_failure_comparison_prompt,
    build_verification_prompt,
)
from .state import FixTestsState


def _get_latest_planner_response(state: FixTestsState) -> str:
    """Get the latest planner agent response from the state messages."""
    messages = state.get("messages", [])

    # Look for the most recent planner response
    for message in reversed(messages):
        if hasattr(message, "content") and message.content:
            # This is a simplified approach - in practice, you might want to
            # track which message came from which agent more explicitly
            if (
                "# Analysis and Planning" in message.content
                or "# File Modifications" in message.content
            ):
                return message.content

    return ""


def _extract_file_modifications_from_response(response: str) -> str:
    """Extract the File Modifications section from a planner response."""
    if not response:
        return ""

    lines = response.split("\n")
    in_file_modifications = False
    modifications_lines = []

    for line in lines:
        if line.strip() == "# File Modifications":
            in_file_modifications = True
            continue
        elif line.startswith("# ") and in_file_modifications:
            # Start of a new section, stop collecting
            break
        elif in_file_modifications:
            modifications_lines.append(line)

    if modifications_lines:
        return "\n".join(modifications_lines).strip()
    else:
        return ""


def _parse_file_bullets_from_todos(todos_content: str) -> list[tuple[str, bool]]:
    """
    Parse + bullets from content to extract file paths and their NEW status.

    Returns:
        List of tuples: (file_path, is_new_file)
    """
    file_bullets = []
    lines = todos_content.split("\n")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("+ "):
            bullet_content = stripped[2:].strip()  # Remove '+ '

            if bullet_content.startswith("NEW "):
                # New file: + NEW path/to/file
                file_path = bullet_content[4:].strip()  # Remove 'NEW '
                file_bullets.append((file_path, True))
            elif bullet_content.startswith("@"):
                # Existing file: + @path/to/file
                file_path = bullet_content[1:].strip()  # Remove '@'
                file_bullets.append((file_path, False))
            # Ignore bullets that don't match expected format

    return file_bullets


def validate_file_paths(state: FixTestsState) -> FixTestsState:
    """
    Validate that file paths in + bullets match reality before running verification agent.

    This checks:
    - Files marked with @path (existing) actually exist
    - Files marked with NEW path (new) do NOT already exist
    """
    print("Validating file paths from planner response...")

    # Get the latest planner response
    planner_response = _get_latest_planner_response(state)

    if not planner_response:
        print("⚠️ Warning: No planner response found - skipping file path validation")
        return state

    try:
        # Extract file modifications section and parse file bullets
        file_modifications = _extract_file_modifications_from_response(planner_response)

        if not file_modifications:
            print(
                "⚠️ Warning: No file modifications found in planner response - skipping file path validation"
            )
            return state

        file_bullets = _parse_file_bullets_from_todos(file_modifications)

        if not file_bullets:
            print("📄 No file bullets found in planner response")
            return state

        # Validate each file path
        validation_errors = []

        for file_path, is_new_file in file_bullets:
            file_exists = os.path.exists(file_path)

            if is_new_file and file_exists:
                validation_errors.append(
                    f"File marked as NEW already exists: {file_path}"
                )
                print(f"❌ Validation error: NEW file already exists: {file_path}")
            elif not is_new_file and not file_exists:
                validation_errors.append(
                    f"File marked as existing does not exist: {file_path}"
                )
                print(f"❌ Validation error: Existing file not found: {file_path}")
            else:
                status = "NEW (non-existent)" if is_new_file else "existing"
                print(f"✅ File path valid: {file_path} ({status})")

        if validation_errors:
            # Add validation errors as verifier notes and trigger editor retry
            updated_verifier_notes = state.get("verifier_notes", []).copy()

            error_note = f"File path validation failed: {'; '.join(validation_errors)}. Please ensure files marked with @ actually exist, and files marked as NEW do not already exist."
            updated_verifier_notes.append(error_note)

            print(
                f"📝 Added file path validation error to verifier notes: {error_note}"
            )

            return {
                **state,
                "verification_passed": False,
                "needs_editor_retry": True,
                "verifier_notes": updated_verifier_notes,
            }
        else:
            print(f"✅ All {len(file_bullets)} file paths validated successfully")
            return state

    except Exception as e:
        print(f"⚠️ Warning: Error during file path validation: {e}")
        # Don't fail the workflow for validation errors - just proceed
        return state


def _revert_rejected_changes(
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


def _clear_completed_todos(artifacts_dir: str) -> None:
    """DEPRECATED: No longer needed since file modifications are passed directly in prompts."""
    # Function kept for compatibility but does nothing
    pass


# Removed _validate_file_paths_in_todos function - no longer needed since file path validation
# is now handled by the validate_file_paths function in the main workflow


def _check_for_duplicate_todos(artifacts_dir: str, current_iteration: int) -> bool:
    """DEPRECATED: No longer needed since file modifications are passed directly in prompts."""
    # Function kept for compatibility but always returns False
    return False


def _create_agent_changes_diff(artifacts_dir: str, iteration: int) -> None:
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
    # Use current_iteration - 1 for editor files since iteration gets incremented by judge/context agents
    # but editor should start numbering from 1
    editor_iteration = state["current_iteration"] - 1
    print_status(
        f"Running editor agent (editor iteration {editor_iteration})...", "progress"
    )

    # File modifications are now passed directly in the prompt from planner response

    # Build prompt for editor
    prompt = build_editor_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="editor",
        iteration=editor_iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Editor agent response received", "success")

    # Save the agent's response with iteration-specific name (for context agent only)
    response_path = os.path.join(
        state["artifacts_dir"], f"editor_iter_{editor_iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Also save as agent_reply.md for current iteration processing by context agent
    agent_reply_path = os.path.join(state["artifacts_dir"], "agent_reply.md")
    with open(agent_reply_path, "w") as f:
        f.write(response.content)

    # File modifications are now passed directly in prompt, no todo completion tracking needed

    # Create a diff of changes made by this agent for the judge to review
    _create_agent_changes_diff(state["artifacts_dir"], editor_iteration)

    return {**state, "messages": state["messages"] + messages + [response]}


def run_test(state: FixTestsState) -> FixTestsState:
    """Run the actual test command and check if it passes."""
    # Use current_iteration - 1 for editor files since iteration gets incremented by judge/context agents
    editor_iteration = state["current_iteration"] - 1
    test_cmd = state["test_cmd"]
    print(f"Running test command (editor iteration {editor_iteration}): {test_cmd}")

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
    # Pipe stdout through trim_test_output if available
    trimmed_stdout = result.stdout
    if result.stdout:
        try:
            trim_result = run_shell_command_with_input(
                "trim_test_output", result.stdout, capture_output=True
            )
            if trim_result.returncode == 0:
                trimmed_stdout = trim_result.stdout
            else:
                print(
                    "Warning: trim_test_output command failed for test output, using original"
                )
        except Exception as e:
            print(f"Warning: Could not trim test output: {e}")

    test_output_content = f"Command: {test_cmd}\nReturn code: {result.returncode}\nSTDOUT:\n{trimmed_stdout}\nSTDERR:\n{result.stderr}\n"
    iter_test_output_path = os.path.join(
        artifacts_dir, f"editor_iter_{editor_iteration}_test_output.txt"
    )
    with open(iter_test_output_path, "w") as f:
        f.write(test_output_content)

    # Add test output to log.md immediately so planner agent can access it
    current_iteration = state["current_iteration"]
    add_test_output_to_log(
        artifacts_dir=artifacts_dir,
        iteration=current_iteration,
        test_output=test_output_content,
        test_output_is_meaningful=True,  # Always true when coming from run_test
    )

    return {**state, "test_passed": test_passed}


def run_verification_agent(state: FixTestsState) -> FixTestsState:
    """Run the verification agent to check if editor changes match todos and have no syntax errors."""
    # Use current_iteration - 1 for editor files since iteration gets incremented by judge/context agents
    editor_iteration = state["current_iteration"] - 1
    verification_retry = state.get("verification_retries", 0)
    print(
        f"Running verification agent (editor iteration {editor_iteration}, verification retry {verification_retry})..."
    )

    # Build prompt for verification
    prompt = build_verification_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="verification",
        iteration=editor_iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Verification agent response received", "success")

    # Save the verification agent's response
    response_path = os.path.join(
        state["artifacts_dir"],
        f"verification_iter_{editor_iteration}_retry_{verification_retry}_response.txt",
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Parse the verification result (expecting format like "VERIFICATION: PASS" or "VERIFICATION: FAIL")
    # Also parse commit message and verifier note if provided
    verification_passed = False
    needs_editor_retry = False
    commit_msg = None
    verifier_note = None
    amend_successful = False  # Initialize to avoid UnboundLocalError
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
        elif line.startswith("COMMIT_MSG:") and verification_passed:
            commit_msg = line.split(":", 1)[1].strip()
            print(f"📝 Commit message: {commit_msg}")
        elif line.startswith("VERIFIER_NOTE:") and not verification_passed:
            verifier_note = line.split(":", 1)[1].strip()
            print(f"📝 Verifier note: {verifier_note}")

    if not verification_passed and not needs_editor_retry:
        # If we couldn't parse the result, assume failure
        needs_editor_retry = True
        print("⚠️ Could not parse verification result - assuming failure")

    # If verification failed and we need to retry editor, clear completed todos and stash changes
    if needs_editor_retry:
        # Add verifier note to accumulated notes if provided
        updated_verifier_notes = state.get("verifier_notes", []).copy()
        if verifier_note:
            updated_verifier_notes.append(verifier_note)
            print(f"📝 Added verifier note to accumulated notes: {verifier_note}")

            # Save the verifier note to artifacts for tracking
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
    elif verification_passed:
        # Mark that verification has succeeded at least once in the workflow instance
        workflow_instance = state.get("workflow_instance")
        if workflow_instance:
            workflow_instance._mark_verification_succeeded()

        # Handle commit logic based on whether this is the first successful verification
        is_first_verification = not state.get("first_verification_success", False)
        use_unamend_first = not is_first_verification

        print(
            f"✅ Successful verification - running {'initial' if is_first_verification else 'subsequent'} commit"
        )

        # Build the new commit message format: @AI(<TAG>) [fix-tests] <MSG> - #<N>
        workflow_tag = state.get("workflow_tag", "XXX")
        commit_iteration = state.get("commit_iteration", 1)

        # Use provided commit message or fallback
        if commit_msg:
            desc_msg = commit_msg
        else:
            desc_msg = f"Editor changes iteration {editor_iteration}"

        full_commit_msg = (
            f"@AI({workflow_tag}) [fix-tests] {desc_msg} - #{commit_iteration}"
        )
        print(f"📝 Full commit message: {full_commit_msg}")

        # Use safe_hg_amend function with proper error handling
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

        # Mark that amend was successful in the workflow instance
        if workflow_instance and amend_successful:
            workflow_instance._mark_amend_successful()

    # Increment commit iteration if this was a successful commit
    new_commit_iteration = state.get("commit_iteration", 1)
    if verification_passed and amend_successful:
        new_commit_iteration += 1

    # Update verifier notes if verification failed
    updated_verifier_notes = state.get("verifier_notes", [])
    if needs_editor_retry and verifier_note:
        updated_verifier_notes = updated_verifier_notes.copy()
        if verifier_note not in updated_verifier_notes:  # Avoid duplicates
            updated_verifier_notes.append(verifier_note)

    return {
        **state,
        "verification_passed": verification_passed,
        "needs_editor_retry": needs_editor_retry,
        "first_verification_success": state.get("first_verification_success", False)
        or verification_passed,
        "last_amend_successful": amend_successful,
        "safe_to_unamend": state.get("safe_to_unamend", False) or amend_successful,
        "commit_iteration": new_commit_iteration,
        "verifier_notes": updated_verifier_notes,
        "messages": state["messages"] + messages + [response],
    }


def run_context_agent(state: FixTestsState) -> FixTestsState:
    """Run the context/planner agent to create editor todos."""
    iteration = state["current_iteration"]
    print(f"Running planner agent (iteration {iteration})...")

    # Build prompt for context agent
    prompt = build_context_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="planner",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Planner agent response received", "success")

    # Save the planner agent's response to a numbered file
    planner_response_path = os.path.join(
        state["artifacts_dir"], f"planner_iter_{iteration}_response.txt"
    )
    with open(planner_response_path, "w") as f:
        f.write(response.content)

    # Validate that planner response contains structured format with + bullets
    artifacts_dir = state["artifacts_dir"]
    file_modifications = _extract_file_modifications_from_response(response.content)

    if not file_modifications:
        # Agent didn't provide structured format
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(
                f"Planner agent failed to provide structured file modifications after {retries} retries - workflow will abort"
            )
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Planner agent failed to provide structured file modifications after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Planner agent didn't provide structured format, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }

    print("✅ Structured file modifications received successfully")

    # Add iteration section to log.md
    try:
        add_iteration_section_to_log(
            artifacts_dir=artifacts_dir,
            iteration=iteration,
            planner_response=response.content,
            todos_content=file_modifications,
        )

    except Exception as e:
        print(f"⚠️ Warning: Failed to add iteration section to log.md: {e}")

    return {
        **state,
        "todos_created": True,  # Always true when we receive structured file modifications
        "research_updated": True,  # research.md is created by research agents now
        "context_agent_retries": 0,  # Reset retries on success
        "current_iteration": state["current_iteration"]
        + 1,  # Increment iteration for next cycle
        "verifier_notes": [],  # Clear verifier notes for new iteration
        "messages": state["messages"] + messages + [response],
    }


def _run_single_research_agent(
    state: FixTestsState, focus: str, title: str, description: str
) -> Dict[str, Any]:
    """Run a single research agent and return its results."""
    iteration = state["current_iteration"]
    artifacts_dir = state["artifacts_dir"]

    print(f"Running {focus.replace('_', ' ')} research agent...")

    # Build prompt for this research agent
    prompt = build_research_prompt(state, focus)

    # Send prompt to Gemini with suppressed output (we'll display after completion)
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type=f"research_{focus}",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
        suppress_output=True,  # Suppress immediate output for parallel execution
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print(f"{focus.replace('_', ' ')} research agent response received")

    # Save the research agent's response
    research_response_path = os.path.join(
        artifacts_dir, f"research_{focus}_iter_{iteration}_response.txt"
    )
    with open(research_response_path, "w") as f:
        f.write(response.content)

    # Return the result for aggregation, including prompt for display
    return {
        "focus": focus,
        "title": title,
        "description": description,
        "content": response.content,
        "prompt": prompt,  # Include prompt for later display
        "messages": messages + [response],
    }


def run_research_agents(state: FixTestsState) -> FixTestsState:
    """Run research agents with different focus areas in parallel and combine results into research.md."""
    iteration = state["current_iteration"]
    print_iteration_header(iteration, "research")
    print_status(
        f"Running research agents in parallel (iteration {iteration})...", "progress"
    )

    research_focuses = [
        (
            "cl_scope",
            "CL Scope Analysis",
            "Analyzing the change list scope and impact on the broader codebase",
        ),
        (
            "similar_tests",
            "Similar Tests Analysis",
            "Finding similar test patterns and examples in the codebase",
        ),
        (
            "test_failure",
            "Test Failure Analysis",
            "Deep analysis of the specific test failure and error messages",
        ),
        (
            "prior_work_analysis",
            "Prior Work Analysis",
            "Investigating previous work and potential issues with prior implementations",
        ),
    ]

    # Add cl_analysis research focus if clquery was provided and clsurf output exists
    if (
        state.get("clquery")
        and state.get("clsurf_output_file")
        and os.path.exists(state["clsurf_output_file"])
    ):
        research_focuses.append(
            (
                "cl_analysis",
                "Previous CL Analysis",
                "Analyzing previous CLs submitted by the author to understand patterns and solutions",
            )
        )
        print_status(
            f"Added CL analysis research agent due to clquery: {state['clquery']}",
            "info",
        )

    research_results = {}
    all_messages = state["messages"]

    # Run all research agents in parallel (up to 5 agents if cl_analysis is included)
    max_workers = len(research_focuses)

    with create_progress_tracker("Research agents", len(research_focuses)) as progress:
        task = progress.add_task(
            "Running research agents...", total=len(research_focuses)
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all research agent tasks
            future_to_focus = {}
            for focus, title, description in research_focuses:
                future = executor.submit(
                    _run_single_research_agent, state, focus, title, description
                )
                future_to_focus[future] = focus

            # Collect results as they complete
            completed_results = []  # Store completed results for display
            for future in as_completed(future_to_focus):
                focus = future_to_focus[future]
                try:
                    result = future.result()

                    # Store the result for aggregation
                    research_results[result["focus"]] = {
                        "title": result["title"],
                        "description": result["description"],
                        "content": result["content"],
                    }

                    # Store completed result for display
                    completed_results.append(result)

                    # Add messages to the overall message list
                    all_messages.extend(result["messages"])

                    print_status(
                        f"{focus.replace('_', ' ')} research agent completed successfully",
                        "success",
                    )

                except Exception as e:
                    print_status(
                        f"{focus.replace('_', ' ')} research agent failed: {e}", "error"
                    )
                    # Create a placeholder result for failed agents
                    research_results[focus] = {
                        "title": f"{focus.replace('_', ' ').title()} (Failed)",
                        "description": f"Research agent failed with error: {e}",
                        "content": f"Error running {focus} research agent: {str(e)}",
                    }

                progress.advance(task)

    print_status("All research agents completed", "success")

    # Now display all prompt/response pairs using Rich formatting
    print_status("Displaying research agent results...", "progress")
    for result in completed_results:
        if "prompt" in result:
            print_prompt_and_response(
                prompt=result["prompt"],
                response=result["content"],
                agent_type=f"research_{result['focus']}",
                iteration=iteration,
                show_prompt=True,
            )

    print_status("Research agent results display completed", "success")

    # Add research findings to log.md immediately so planner agent can access them
    add_research_to_log(
        artifacts_dir=state["artifacts_dir"],
        iteration=iteration,
        research_results=research_results,
    )

    # Clean up any local changes made by research agents
    print("Cleaning up any local changes made by research agents...")
    cleanup_result = run_shell_command("hg update --clean .", capture_output=True)
    if cleanup_result.returncode == 0:
        print("✅ Successfully cleaned up local changes from research agents")
    else:
        print(f"⚠️ Warning: Failed to clean up local changes: {cleanup_result.stderr}")

    return {
        **state,
        "research_results": research_results,
        "research_md_created": True,
        "messages": all_messages,
    }


def run_postmortem_agent(state: FixTestsState) -> FixTestsState:
    """Run postmortem agent to analyze why the last iteration failed to make meaningful progress."""
    iteration = state["current_iteration"]
    print(f"Running postmortem agent (iteration {iteration})...")

    # Build prompt for postmortem agent
    prompt = _build_postmortem_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="postmortem",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Postmortem agent response received", "success")

    # Save the postmortem agent's response
    postmortem_response_path = os.path.join(
        state["artifacts_dir"], f"postmortem_iter_{iteration}_response.txt"
    )
    with open(postmortem_response_path, "w") as f:
        f.write(response.content)

    # Add postmortem analysis to log.md immediately so planner agent can access it
    add_postmortem_to_log(
        artifacts_dir=state["artifacts_dir"],
        iteration=iteration,
        postmortem_content=response.content,
    )

    return {
        **state,
        "postmortem_completed": True,
        "postmortem_content": response.content,
        "messages": state["messages"] + messages + [response],
    }


def _build_postmortem_prompt(state: FixTestsState) -> str:
    """Build the prompt for the postmortem agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    # Get the last editor iteration number
    last_editor_iteration = iteration - 1

    prompt = f"""You are a postmortem analysis agent (iteration {iteration}). Your goal is to analyze why the previous iteration failed to make meaningful progress in fixing the test failure.

# CONTEXT:
The test failure comparison agent determined that the test output from iteration {last_editor_iteration} was not meaningfully different from previous test outputs. This suggests that the last editor iteration either:
1. Made no effective changes to fix the underlying issue
2. Made changes that didn't address the root cause
3. Made changes that introduced new issues but didn't resolve the original problem
4. Made changes that were syntactically correct but logically ineffective

# YOUR ANALYSIS FOCUS:
Investigate what went wrong with iteration {last_editor_iteration} and why it failed to make meaningful progress.

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes
@{artifacts_dir}/cl_desc.txt - Current CL description"""

    # Add previous iteration files
    for iter_num in range(1, iteration):
        prompt += f"""
- @{artifacts_dir}/planner_iter_{iter_num}_response.txt - Planner response for iteration {iter_num}
- @{artifacts_dir}/editor_iter_{iter_num}_response.txt - Editor response for iteration {iter_num}
- @{artifacts_dir}/editor_iter_{iter_num}_changes.diff - Code changes from iteration {iter_num}
- @{artifacts_dir}/editor_iter_{iter_num}_test_output.txt - Test output from iteration {iter_num}"""

        # Add todos file if it exists
        todos_file = os.path.join(artifacts_dir, f"editor_iter_{iter_num}_todos.txt")
        if os.path.exists(todos_file):
            prompt += f"""
- @{artifacts_dir}/editor_iter_{iter_num}_todos.txt - Todo list for iteration {iter_num}"""

    prompt += f"""

# ANALYSIS QUESTIONS TO ANSWER:
1. **What was the planner's strategy for iteration {last_editor_iteration}?**
   - Review the planner response and todo list
   - Was the strategy sound or flawed?
   - Did it address the right root causes?

2. **How well did the editor execute the plan?**
   - Review the editor response and actual code changes
   - Did the editor complete all todos as requested?
   - Were the code changes technically correct?
   - Did the editor make any obvious mistakes?

3. **Why didn't the changes fix the test failure?**
   - Compare the test outputs before and after the iteration
   - What specific aspects of the test failure remained unchanged?
   - Were the changes addressing symptoms rather than root causes?

4. **What patterns emerge from previous iterations?**
   - Are we stuck in a loop of similar unsuccessful approaches?
   - Have we been avoiding certain types of changes that might be necessary?
   - Are there recurring themes in the failures?

5. **What should be done differently in the next iteration?**
   - What alternative approaches should be considered?
   - What assumptions should be questioned?
   - What areas need deeper investigation?

# RESPONSE FORMAT:
Structure your postmortem analysis as follows:

## Iteration {last_editor_iteration} Strategy Analysis
- Analyze the planner's approach and todo list
- Assess whether the strategy was appropriate for the problem

## Editor Execution Analysis  
- Review how well the editor executed the plan
- Identify any execution issues or deviations from the plan

## Root Cause Analysis
- Analyze why the changes didn't fix the test failure
- Compare test outputs to identify what didn't change

## Pattern Recognition
- Identify recurring patterns or themes across iterations
- Note if we're stuck in unproductive loops

## Recommendations for Next Iteration
- Specific suggestions for alternative approaches
- Areas that need deeper investigation or different strategies
- Assumptions that should be reconsidered

# IMPORTANT NOTES:
- Focus on actionable insights for improving the next iteration
- Be specific about what went wrong and why
- Avoid generic advice - provide concrete analysis based on the specific iteration
- Look for root causes, not just symptoms
- Consider whether the approach has been too narrow or missing key areas"""

    # Add user instructions if available
    user_instructions_content = ""
    if state.get("user_instructions_file") and os.path.exists(
        state["user_instructions_file"]
    ):
        try:
            with open(state["user_instructions_file"], "r") as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")

    if user_instructions_content:
        prompt += f"""

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""

    return prompt


def run_test_failure_comparison_agent(state: FixTestsState) -> FixTestsState:
    """Run agent to compare current test failure with previous test failure and determine if research agents should be re-run."""
    iteration = state["current_iteration"]
    print(f"Running test failure comparison agent (iteration {iteration})...")

    artifacts_dir = state["artifacts_dir"]
    distinct_test_outputs = state.get("distinct_test_outputs", [])

    print(
        f"Comparing current test failure against {len(distinct_test_outputs)} previous distinct test outputs"
    )

    # Build prompt for test failure comparison agent
    prompt = build_test_failure_comparison_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="test_failure_comparison",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Test failure comparison agent response received", "success")

    # Save the comparison agent's response
    comparison_response_path = os.path.join(
        artifacts_dir, f"test_failure_comparison_iter_{iteration}_response.txt"
    )
    with open(comparison_response_path, "w") as f:
        f.write(response.content)

    # Parse the comparison result (expecting format like "MEANINGFUL_CHANGE: YES" or "MEANINGFUL_CHANGE: NO")
    meaningful_change = False
    lines = response.content.split("\n")

    for line in lines:
        if line.startswith("MEANINGFUL_CHANGE:"):
            result = line.split(":", 1)[1].strip().upper()
            if result in ["YES", "TRUE", "1"]:
                meaningful_change = True
                print("✅ Novel test failure detected - research agents will be re-run")
            else:
                meaningful_change = False
                print(
                    "✅ Test failure matches previous distinct failure - skipping research agents"
                )
            break

    if "MEANINGFUL_CHANGE:" not in response.content:
        # If we couldn't parse the result, assume meaningful change for safety
        meaningful_change = True
        print("⚠️ Could not parse comparison result - assuming novel failure")

    # If this is a meaningful change, add current test output to distinct list
    updated_distinct_test_outputs = distinct_test_outputs.copy()
    if meaningful_change:
        current_test_output = os.path.join(artifacts_dir, "test_output.txt")
        # Create a permanent copy of the current test output with iteration info
        distinct_test_output_path = os.path.join(
            artifacts_dir, f"distinct_test_output_iter_{iteration}.txt"
        )
        try:
            import shutil

            shutil.copy2(current_test_output, distinct_test_output_path)
            updated_distinct_test_outputs.append(distinct_test_output_path)
            print(
                f"✅ Added current test failure to distinct outputs: {distinct_test_output_path}"
            )
        except Exception as e:
            print(f"⚠️ Warning: Failed to create distinct test output copy: {e}")

    return {
        **state,
        "meaningful_test_failure_change": meaningful_change,
        "comparison_completed": True,
        "distinct_test_outputs": updated_distinct_test_outputs,
        "messages": state["messages"] + messages + [response],
    }
