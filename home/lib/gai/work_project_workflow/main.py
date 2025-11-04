"""Main workflow class for work-project workflow."""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langgraph.graph import END, START, StateGraph
from workflow_base import BaseWorkflow

from .state import WorkProjectState
from .workflow_nodes import (
    handle_failure,
    handle_success,
    initialize_work_project_workflow,
    invoke_create_cl,
    select_next_changespec,
)


class WorkProjectWorkflow(BaseWorkflow):
    """A workflow for processing ProjectSpec files to create the next CL."""

    def __init__(
        self, project_file: str, design_docs_dir: str, dry_run: bool = False
    ) -> None:
        """
        Initialize the work-project workflow.

        Args:
            project_file: Path to the ProjectSpec file (e.g., ~/.gai/projects/yserve.md)
            design_docs_dir: Directory containing markdown design documents
            dry_run: If True, only print the ChangeSpec without invoking create-cl
        """
        self.project_file = project_file
        self.design_docs_dir = design_docs_dir
        self.dry_run = dry_run
        self._current_state: WorkProjectState | None = None

    @property
    def name(self) -> str:
        """Return the workflow name."""
        return "work-project"

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

        # Add edges
        workflow.add_edge(START, "initialize")

        # Handle initialization failure
        workflow.add_conditional_edges(
            "initialize",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "select_next"},
        )

        # Handle selection failure
        workflow.add_conditional_edges(
            "select_next",
            lambda state: "failure" if state.get("failure_reason") else "continue",
            {"failure": "failure", "continue": "invoke_create_cl"},
        )

        # Handle create-cl invocation
        workflow.add_conditional_edges(
            "invoke_create_cl",
            lambda state: "success" if state.get("success") else "failure",
            {"success": "success", "failure": "failure"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def _update_current_state(self, state: "WorkProjectState") -> None:
        """Store the current state for interrupt handling."""
        self._current_state = state

    def _revert_changespec_status(self, state: "WorkProjectState") -> None:
        """Revert the ChangeSpec STATUS back to 'Not Started' after interrupt."""
        from rich_utils import print_status

        selected_changespec = state.get("selected_changespec")
        if not selected_changespec:
            return

        cs_name = selected_changespec.get("NAME", "")
        if not cs_name:
            return

        project_file = state.get("project_file", self.project_file)

        try:
            from .workflow_nodes import _update_changespec_status

            _update_changespec_status(project_file, cs_name, "Not Started")
            print_status(f"Reverted STATUS to 'Not Started' for {cs_name}", "success")
        except Exception as e:
            print_status(f"Failed to revert STATUS for {cs_name}: {e}", "error")

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        from rich_utils import print_status, print_workflow_header

        # Print workflow header
        print_workflow_header("work-project", "")

        # Validate project file exists
        if not os.path.isfile(self.project_file):
            print_status(f"Project file '{self.project_file}' does not exist", "error")
            return False

        # Validate design docs directory exists
        if not os.path.isdir(self.design_docs_dir):
            print_status(
                f"Design docs directory '{self.design_docs_dir}' does not exist or is not a directory",
                "error",
            )
            return False

        final_state = None
        try:
            # Create and run the workflow
            app = self.create_workflow()

            initial_state: WorkProjectState = {
                "project_file": self.project_file,
                "design_docs_dir": self.design_docs_dir,
                "dry_run": self.dry_run,
                "project_name": "",  # Will be set during initialization
                "changespecs": [],
                "selected_changespec": None,
                "status_updated_to_in_progress": False,
                "success": False,
                "failure_reason": None,
                "workflow_instance": self,
            }

            final_state = app.invoke(initial_state)

            return final_state["success"]
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

            return False
        except Exception as e:
            from rich_utils import print_status

            print_status(f"Error running work-project workflow: {e}", "error")

            # Also try to revert STATUS on general errors
            current_state = self._current_state or final_state
            if current_state and current_state.get("status_updated_to_in_progress"):
                self._revert_changespec_status(current_state)

            return False
