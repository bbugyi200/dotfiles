"""Main workflow class for work-projects workflow."""

import os
import sys
import time
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from shared_utils import LANGGRAPH_RECURSION_LIMIT
from workflow_base import BaseWorkflow

from .state import WorkProjectState
from .workflow_nodes import (
    check_continuation,
    handle_failure,
    handle_success,
    initialize_work_project_workflow,
    invoke_create_cl,
    select_next_changespec,
)


class WorkProjectWorkflow(BaseWorkflow):
    """A workflow for processing ProjectSpec files to create the next CL."""

    def __init__(
        self,
        yolo: bool = False,
        max_changespecs: int | None = None,
        include_filters: list[str] | None = None,
    ) -> None:
        """
        Initialize the work-projects workflow.

        Args:
            yolo: If True, skip confirmation prompts and process all ChangeSpecs automatically
            max_changespecs: Maximum number of ChangeSpecs to process (None = infinity)
            include_filters: List of status categories to include (blocked, unblocked, wip).
                           None = include all ChangeSpecs regardless of status.
        """
        self.yolo = yolo
        self.max_changespecs = max_changespecs
        self.include_filters = include_filters or []
        self._current_state: WorkProjectState | None = None
        # Track all ChangeSpecs set to intermediate states for cleanup
        # Maps (project_file, changespec_name) -> {status: str, tdd_cl_created: bool}
        self._intermediate_states: dict[tuple[str, str], dict[str, Any]] = {}

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "work"

    @property
    def description(self) -> str:
        """Return the workflow description."""
        return "Process a ProjectSpec file to create the next CL"

    def create_workflow(self) -> Any:
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(WorkProjectState)

        # Add nodes
        workflow.add_node("initialize", initialize_work_project_workflow)
        workflow.add_node("select_next", select_next_changespec)
        workflow.add_node("invoke_create_cl", invoke_create_cl)
        workflow.add_node("success", handle_success)
        workflow.add_node("failure", handle_failure)
        workflow.add_node("check_continuation", check_continuation)

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure (only happens once at start)
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": END, "continue": "select_next"},
        )

        # Handle selection - if no ChangeSpec found, end workflow
        workflow.add_conditional_edges(
            "select_next",
            lambda state: (
                "no_changespec" if state.get("failure_reason") else "continue"
            ),
            {"no_changespec": END, "continue": "invoke_create_cl"},
        )

        # Handle create-cl invocation
        workflow.add_conditional_edges(
            "invoke_create_cl",
            lambda state: "success" if state.get("success") else "failure",
            {"success": "success", "failure": "failure"},
        )

        # After success/failure, check if we should continue
        workflow.add_edge("success", "check_continuation")
        workflow.add_edge("failure", "check_continuation")

        # Check continuation - either loop back or end
        workflow.add_conditional_edges(
            "check_continuation",
            lambda state: "continue" if state.get("should_continue") else "end",
            {"continue": "select_next", "end": END},
        )

        return workflow.compile()

    def _update_current_state(self, state: "WorkProjectState") -> None:
        """Store the current state for interrupt handling."""
        self._current_state = state

    def _track_intermediate_state(
        self,
        project_file: str,
        changespec_name: str,
        status: str,
        tdd_cl_created: bool = False,
    ) -> None:
        """Track a ChangeSpec that has been set to an intermediate state.

        Args:
            project_file: Path to the project file
            changespec_name: Name of the ChangeSpec
            status: The intermediate status ("In Progress" or "Fixing Tests")
            tdd_cl_created: Whether "TDD CL Created" was reached (only relevant for "In Progress")
        """
        key = (project_file, changespec_name)
        self._intermediate_states[key] = {
            "status": status,
            "tdd_cl_created": tdd_cl_created,
        }

    def _untrack_intermediate_state(
        self, project_file: str, changespec_name: str
    ) -> None:
        """Remove a ChangeSpec from intermediate state tracking (reached final state).

        Args:
            project_file: Path to the project file
            changespec_name: Name of the ChangeSpec
        """
        key = (project_file, changespec_name)
        if key in self._intermediate_states:
            del self._intermediate_states[key]

    def _cleanup_all_intermediate_states(self) -> None:
        """Clean up all ChangeSpecs that are still in intermediate states.

        This should be called when the workflow exits (in a finally block) to ensure
        no ChangeSpecs are left in "In Progress" or "Fixing Tests" states.
        """
        from rich_utils import print_status
        from status_state_machine import transition_changespec_status

        if not self._intermediate_states:
            return

        print_status(
            f"\nCleaning up {len(self._intermediate_states)} ChangeSpec(s) in intermediate states...",
            "warning",
        )

        for (project_file, cs_name), details in self._intermediate_states.items():
            status = details["status"]
            tdd_cl_created = details.get("tdd_cl_created", False)

            # Determine target status based on current state
            if status == "Fixing Tests":
                target_status = "TDD CL Created"
                reason = "workflow did not complete fix-tests phase"
            elif status == "In Progress":
                if tdd_cl_created:
                    # Test CL was created successfully, keep "TDD CL Created" status
                    print_status(
                        f"Keeping STATUS as 'TDD CL Created' for {cs_name} (test CL completed)",
                        "info",
                    )
                    continue
                else:
                    target_status = "Not Started"
                    reason = "workflow did not complete create-test-cl phase"
            else:
                print_status(
                    f"Warning: Unexpected intermediate state '{status}' for {cs_name}",
                    "warning",
                )
                continue

            # Revert the status (use validate=False to allow rollback)
            success, _, error = transition_changespec_status(
                project_file, cs_name, target_status, validate=False
            )
            if success:
                print_status(
                    f"Reverted STATUS to '{target_status}' for {cs_name} ({reason})",
                    "success",
                )
            else:
                print_status(
                    f"Failed to revert STATUS for {cs_name}: {error}",
                    "error",
                )

    def _revert_changespec_status(self, state: "WorkProjectState") -> None:
        """Revert the ChangeSpec STATUS after interrupt.

        Reversion logic:
        - If "Fixing Tests" was set: revert to "TDD CL Created"
        - If "In Progress" was set but "TDD CL Created" was not: revert to "Not Started"
        - Otherwise: keep current status (work completed successfully)
        """
        from rich_utils import print_status

        selected_changespec = state.get("selected_changespec")
        if not selected_changespec:
            return

        cs_name = selected_changespec.get("NAME", "")
        if not cs_name:
            return

        project_file = state.get("project_file", "")

        # Check if we updated to "Fixing Tests" - if so, revert to "TDD CL Created"
        if state.get("status_updated_to_fixing_tests"):
            from status_state_machine import transition_changespec_status

            success, _, error = transition_changespec_status(
                project_file, cs_name, "TDD CL Created", validate=False
            )
            if success:
                print_status(
                    f"Reverted STATUS to 'TDD CL Created' for {cs_name}", "success"
                )
            else:
                print_status(f"Failed to revert STATUS for {cs_name}: {error}", "error")
            return

        # Check if we updated to "In Progress" but not yet to "TDD CL Created"
        if not state.get("status_updated_to_in_progress"):
            return

        if state.get("status_updated_to_tdd_cl_created"):
            # create-test-cl completed successfully, keep "TDD CL Created" status
            print_status(
                f"Keeping STATUS as 'TDD CL Created' for {cs_name} (create-test-cl completed)",
                "info",
            )
            return

        # Revert to "Not Started" (create-test-cl didn't complete)
        from status_state_machine import transition_changespec_status

        success, _, error = transition_changespec_status(
            project_file, cs_name, "Not Started", validate=False
        )
        if success:
            print_status(f"Reverted STATUS to 'Not Started' for {cs_name}", "success")
        else:
            print_status(f"Failed to revert STATUS for {cs_name}: {error}", "error")

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        from pathlib import Path

        from rich_utils import print_status, print_workflow_header

        # Print workflow header
        print_workflow_header("work", "")

        # Get all project files from ~/.gai/projects
        projects_dir = os.path.expanduser("~/.gai/projects")
        if not os.path.isdir(projects_dir):
            print_status(
                f"Projects directory '{projects_dir}' does not exist or is not a directory",
                "error",
            )
            return False

        project_files = sorted(Path(projects_dir).glob("*.md"))
        if not project_files:
            print_status(f"No project files found in {projects_dir}", "error")
            return False

        # Get environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            print_status("GOOG_CLOUD_DIR environment variable is not set", "error")
            return False

        if not goog_src_dir_base:
            print_status("GOOG_SRC_DIR_BASE environment variable is not set", "error")
            return False

        total_processed = 0
        any_success = False
        # Track attempted ChangeSpecs globally across all project files
        global_attempted_changespecs: list[str] = []
        global_attempted_changespec_statuses: dict[str, str] = {}

        try:
            # Loop until all ChangeSpecs in all project files are in unworkable states
            while True:
                workable_found = False
                iteration_start_count = total_processed

                for project_file in project_files:
                    # Brief sleep to allow Python to process signals
                    time.sleep(0.01)

                    project_file_str = str(project_file)

                    # Check if this project file has any workable ChangeSpecs
                    if not self._has_workable_changespecs(project_file_str):
                        continue

                    workable_found = True

                    # Extract project name from filename (basename without extension)
                    project_name = project_file.stem

                    # Change to the project directory
                    project_dir = os.path.join(
                        goog_cloud_dir, project_name, goog_src_dir_base
                    )
                    if not os.path.isdir(project_dir):
                        print_status(
                            f"Project directory '{project_dir}' does not exist. Skipping project '{project_name}'.",
                            "warning",
                        )
                        continue

                    try:
                        os.chdir(project_dir)
                    except Exception as e:
                        print_status(
                            f"Failed to change to directory '{project_dir}': {e}",
                            "error",
                        )
                        continue

                    # Process this project file
                    (
                        success,
                        global_attempted_changespecs,
                        global_attempted_changespec_statuses,
                    ) = self._process_project_file(
                        project_file_str,
                        global_attempted_changespecs,
                        global_attempted_changespec_statuses,
                    )
                    if success:
                        any_success = True
                        total_processed += 1

                # If no workable ChangeSpecs were found in any project file, we're done
                if not workable_found:
                    print_status(
                        "\nAll ChangeSpecs in all project files are in unworkable states.",
                        "success",
                    )
                    break

                # If we made no progress in this iteration (processed 0 ChangeSpecs),
                # break to avoid infinite loop
                if total_processed == iteration_start_count:
                    print_status(
                        "\nNo progress made in this iteration. All workable ChangeSpecs have been attempted.",
                        "info",
                    )
                    break

            return any_success
        except KeyboardInterrupt:
            print_status("\n\nWorkflow interrupted by user (Ctrl+C)", "warning")
            return False
        finally:
            # Always clean up any ChangeSpecs left in intermediate states
            self._cleanup_all_intermediate_states()

    def _has_workable_changespecs(self, project_file: str) -> bool:
        """
        Check if a project file has any ChangeSpecs in workable states.

        Workable states: Not Started, TDD CL Created, In Progress, Fixing Tests
        Unworkable states: Pre-Mailed, Failed to Create CL, Failed to Fix Tests, Mailed, Submitted

        If include_filters is specified, only ChangeSpecs matching the filter will be considered workable.
        """
        from rich_utils import print_status

        from work_projects_workflow.workflow_nodes import _get_statuses_for_filters

        if not os.path.isfile(project_file):
            return False

        try:
            with open(project_file) as f:
                content = f.read()

            _, changespecs = self._parse_project_spec(content)

            # Get the set of statuses to include based on filters
            allowed_statuses = _get_statuses_for_filters(self.include_filters)

            if allowed_statuses:
                # If filters specified, check if any ChangeSpec has a matching status
                for cs in changespecs:
                    status = cs.get("STATUS", "").strip()
                    if status in allowed_statuses:
                        return True
                return False
            else:
                # No filters - use original logic (exclude unworkable states)
                unworkable_states = {
                    "Pre-Mailed",
                    "Failed to Create CL",
                    "Failed to Fix Tests",
                    "Mailed",
                    "Submitted",
                }

                for cs in changespecs:
                    status = cs.get("STATUS", "").strip()
                    if status not in unworkable_states:
                        return True

                return False
        except Exception as e:
            print_status(
                f"Error checking workable ChangeSpecs in {project_file}: {e}", "warning"
            )
            return False

    def _parse_project_spec(
        self, content: str
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Import and use the parsing function from workflow_nodes."""
        from .workflow_nodes import _parse_project_spec

        return _parse_project_spec(content)

    def _process_project_file(
        self,
        project_file: str,
        global_attempted_changespecs: list[str],
        global_attempted_changespec_statuses: dict[str, str],
    ) -> tuple[bool, list[str], dict[str, str]]:
        """Process a single project file.

        Args:
            project_file: Path to the project file to process
            global_attempted_changespecs: List of ChangeSpec names attempted across all project files
            global_attempted_changespec_statuses: Dict mapping ChangeSpec names to their last attempted STATUS

        Returns:
            Tuple of (success, updated_global_attempted_changespecs, updated_global_attempted_changespec_statuses)
        """
        from pathlib import Path

        from rich_utils import print_status

        # Validate project file exists
        if not os.path.isfile(project_file):
            print_status(f"Project file '{project_file}' does not exist", "error")
            return (
                False,
                global_attempted_changespecs,
                global_attempted_changespec_statuses,
            )

        # Derive design docs directory from project file basename
        # Example: ~/.gai/projects/yserve.md -> ~/.gai/designs/yserve/
        project_path = Path(project_file)
        design_docs_dir = os.path.expanduser(f"~/.gai/designs/{project_path.stem}")

        # Validate design docs directory exists
        if not os.path.isdir(design_docs_dir):
            print_status(
                f"Design docs directory '{design_docs_dir}' does not exist or is not a directory",
                "error",
            )
            return (
                False,
                global_attempted_changespecs,
                global_attempted_changespec_statuses,
            )

        final_state = None
        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: WorkProjectState = {
                "project_file": project_file,
                "design_docs_dir": design_docs_dir,
                "yolo": self.yolo,
                "include_filters": self.include_filters,
                "bug_id": "",  # Will be set during initialization
                "project_name": "",  # Will be set during initialization
                "changespecs": [],
                "selected_changespec": None,
                "cl_name": "",  # Will be set during select_next
                "cl_description": "",  # Will be set during select_next
                "artifacts_dir": "",  # Will be set during select_next
                "workflow_tag": "",  # Will be set during select_next
                "clsurf_output_file": None,  # Will be set during select_next
                "cl_id": None,  # Will be set after successful CL creation
                "messages": [],
                "status_updated_to_in_progress": False,
                "status_updated_to_tdd_cl_created": False,
                "status_updated_to_fixing_tests": False,
                "success": False,
                "failure_reason": None,
                "attempted_changespecs": global_attempted_changespecs,
                "attempted_changespec_statuses": global_attempted_changespec_statuses,
                "max_changespecs": self.max_changespecs,
                "changespecs_processed": 0,
                "should_continue": False,
                "changespec_history": [],  # Track ChangeSpec navigation history
                "current_changespec_index": -1,  # Current position in history (-1 = none selected)
                "total_eligible_changespecs": 0,  # Will be calculated during select_next
                "user_requested_quit": False,  # User requested to quit
                "user_requested_prev": False,  # User requested to go to previous
                "workflow_instance": self,
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            # Return True if at least one ChangeSpec was successfully processed
            changespecs_processed = final_state.get("changespecs_processed", 0)
            attempted_changespecs = final_state.get("attempted_changespecs", [])
            attempted_changespec_statuses = final_state.get(
                "attempted_changespec_statuses", {}
            )

            # Return True if at least one ChangeSpec was successfully processed
            return (
                changespecs_processed > 0,
                attempted_changespecs,
                attempted_changespec_statuses,
            )
        except KeyboardInterrupt:
            from rich_utils import print_status

            print_status("\n\nWorkflow interrupted by user", "warning")

            # Revert STATUS back to "Not Started" if we updated it
            current_state = self._current_state or final_state
            if current_state and current_state.get("status_updated_to_in_progress"):
                self._revert_changespec_status(current_state)
            elif not current_state:
                # Workflow was interrupted before any state was captured
                print_status(
                    "Note: If a ChangeSpec was set to 'In Progress', you may need to manually revert it to 'Not Started'",
                    "warning",
                )

            # Re-raise the exception so it propagates to the outer loop
            raise
        except Exception as e:
            from rich_utils import print_status

            print_status(
                f"Error running work-projects workflow for {project_file}: {e}", "error"
            )

            # Also try to revert STATUS on general errors
            current_state = self._current_state or final_state
            if current_state and current_state.get("status_updated_to_in_progress"):
                self._revert_changespec_status(current_state)

            return (
                False,
                global_attempted_changespecs,
                global_attempted_changespec_statuses,
            )
