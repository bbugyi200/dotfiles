"""Main workflow class for work-projects workflow."""

import os
import sys
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
        dry_run: bool = False,
        max_changespecs: int | None = None,
    ) -> None:
        """
        Initialize the work-projects workflow.

        Args:
            dry_run: If True, only print the ChangeSpec without invoking create-cl
            max_changespecs: Maximum number of ChangeSpecs to process (None = infinity)
        """
        self.dry_run = dry_run
        self.max_changespecs = max_changespecs
        self._current_state: WorkProjectState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "work-projects"

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
            try:
                from .workflow_nodes import _update_changespec_status

                _update_changespec_status(project_file, cs_name, "TDD CL Created")
                print_status(
                    f"Reverted STATUS to 'TDD CL Created' for {cs_name}", "success"
                )
            except Exception as e:
                print_status(f"Failed to revert STATUS for {cs_name}: {e}", "error")
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
        try:
            from .workflow_nodes import _update_changespec_status

            _update_changespec_status(project_file, cs_name, "Not Started")
            print_status(f"Reverted STATUS to 'Not Started' for {cs_name}", "success")
        except Exception as e:
            print_status(f"Failed to revert STATUS for {cs_name}: {e}", "error")

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        from pathlib import Path

        from rich_utils import print_status, print_workflow_header

        # Print workflow header
        print_workflow_header("work-projects", "")

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

        print_status(
            f"Found {len(project_files)} project file(s) in {projects_dir}", "info"
        )

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

        try:
            # Loop until all ChangeSpecs in all project files are in unworkable states
            while True:
                workable_found = False
                iteration_start_count = total_processed

                for project_file in project_files:
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

                    print_status(
                        f"\nChanging to project directory: {project_dir}", "info"
                    )
                    try:
                        os.chdir(project_dir)
                        print_status(
                            f"Successfully changed to: {os.getcwd()}", "success"
                        )
                    except Exception as e:
                        print_status(
                            f"Failed to change to directory '{project_dir}': {e}",
                            "error",
                        )
                        continue

                    print_status(
                        f"\nProcessing project file: {project_file_str}", "info"
                    )

                    # Process this project file
                    success = self._process_project_file(project_file_str)
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
                # break to avoid infinite loop (can happen in dry-run when STATUS never changes)
                if total_processed == iteration_start_count:
                    print_status(
                        "\nNo progress made in this iteration. All workable ChangeSpecs have been attempted.",
                        "info",
                    )
                    break

            print_status(f"\nTotal projects processed: {total_processed}", "info")
            return any_success
        except KeyboardInterrupt:
            print_status("\n\nWorkflow interrupted by user (Ctrl+C)", "warning")
            return False

    def _has_workable_changespecs(self, project_file: str) -> bool:
        """
        Check if a project file has any ChangeSpecs in workable states.

        Workable states: Not Started, TDD CL Created, In Progress, Fixing Tests
        Unworkable states: Pre-Mailed, Failed to Create CL, Failed to Fix Tests, Mailed, Submitted
        """
        from rich_utils import print_status

        if not os.path.isfile(project_file):
            return False

        try:
            with open(project_file) as f:
                content = f.read()

            _, changespecs = self._parse_project_spec(content)

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

    def _process_project_file(self, project_file: str) -> bool:
        """Process a single project file."""
        from pathlib import Path

        from rich_utils import print_status

        # Validate project file exists
        if not os.path.isfile(project_file):
            print_status(f"Project file '{project_file}' does not exist", "error")
            return False

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
            return False

        print_status(f"Using design docs directory: {design_docs_dir}", "info")

        final_state = None
        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: WorkProjectState = {
                "project_file": project_file,
                "design_docs_dir": design_docs_dir,
                "dry_run": self.dry_run,
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
                "attempted_changespecs": [],
                "attempted_changespec_statuses": {},
                "max_changespecs": self.max_changespecs,
                "changespecs_processed": 0,
                "should_continue": False,
                "workflow_instance": self,
            }

            final_state = app.invoke(
                initial_state, config={"recursion_limit": LANGGRAPH_RECURSION_LIMIT}
            )

            # Print final summary
            changespecs_processed = final_state.get("changespecs_processed", 0)
            attempted_changespecs = final_state.get("attempted_changespecs", [])

            print_status(
                f"\nWorkflow completed for {project_file}. Processed {changespecs_processed} ChangeSpec(s).",
                "info",
            )
            if attempted_changespecs:
                print_status(
                    f"Attempted ChangeSpecs: {', '.join(attempted_changespecs)}", "info"
                )

            # Return True if at least one ChangeSpec was successfully processed
            return changespecs_processed > 0
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

            return False
