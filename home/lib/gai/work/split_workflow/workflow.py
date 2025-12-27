"""Workflow for splitting a CL into multiple smaller CLs."""

import os
from pathlib import Path

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console
from rich_utils import print_status, print_workflow_header
from running_field import claim_workspace, release_workspace
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_shell_command,
)
from split_spec import parse_split_spec, validate_split_spec
from workflow_base import BaseWorkflow

from work.changespec import find_all_changespecs

from .agent import build_split_prompt, generate_spec_with_agent
from .spec import create_and_edit_spec, load_and_archive_spec
from .utils import (
    generate_timestamp,
    get_name_from_branch,
    get_project_file_and_workspace_info,
    has_children,
    prompt_for_revert,
)


class SplitWorkflow(BaseWorkflow):
    """A workflow for splitting a CL into multiple smaller CLs."""

    def __init__(
        self,
        name: str | None,
        spec_path: str | None,
        create_spec: bool,
        generate_spec: bool = False,
    ) -> None:
        """Initialize the split workflow.

        Args:
            name: Name of the ChangeSpec to split (or None to use current branch).
            spec_path: Path to an existing SplitSpec file (or None).
            create_spec: If True, create a new spec file and open in editor.
            generate_spec: If True, use an agent to generate the spec.
        """
        self._cl_name = name
        self._spec_path = spec_path
        self._create_spec = create_spec
        self._generate_spec = generate_spec

    @property
    def name(self) -> str:
        return "split"

    @property
    def description(self) -> str:
        return "Split a CL into multiple smaller CLs"

    def run(self) -> bool:
        """Execute the split workflow.

        Returns:
            True if successful, False otherwise.
        """
        console = Console()
        workflow_tag = generate_workflow_tag()

        # Print workflow header
        print_workflow_header("split", workflow_tag)

        # Step 1: Determine NAME (from arg or branch_name)
        cl_name = self._cl_name
        if cl_name is None:
            cl_name = get_name_from_branch()
            if cl_name is None:
                print_status(
                    "Could not determine CL name from branch. Please provide NAME.",
                    "error",
                )
                return False
            print_status(f"Using current branch: {cl_name}", "info")

        # Step 2: Validate target CL has no children
        print_status("Checking for child CLs...", "progress")
        if has_children(cl_name):
            print_status(
                f"Cannot split: CL '{cl_name}' has child CLs. "
                "Split child CLs first or restructure the hierarchy.",
                "error",
            )
            return False
        print_status("No child CLs found.", "success")

        # Generate timestamp for archiving
        timestamp = generate_timestamp()

        # Step 3: Navigate to target CL (needed for diff before spec generation)
        print_status(f"Navigating to CL: {cl_name}...", "progress")
        nav_result = run_shell_command(f"bb_hg_update {cl_name}", capture_output=True)
        if nav_result.returncode != 0:
            print_status(f"Failed to navigate to CL: {nav_result.stderr}", "error")
            return False
        print_status(f"Now on CL: {cl_name}", "success")

        # Step 4: Save diff and gather metadata
        print_status("Saving diff and gathering metadata...", "progress")

        # Create bb/gai directory if needed
        bb_gai_dir = "bb/gai"
        Path(bb_gai_dir).mkdir(parents=True, exist_ok=True)

        # Save diff
        diff_path = f"{bb_gai_dir}/{cl_name}.diff"
        diff_result = run_shell_command("branch_diff", capture_output=True)
        if diff_result.returncode != 0:
            print_status(f"Failed to get branch diff: {diff_result.stderr}", "error")
            return False
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_result.stdout)
        print_status(f"Diff saved to: {diff_path}", "success")

        # Get bug number
        bug_result = run_shell_command("branch_bug", capture_output=True)
        if bug_result.returncode != 0:
            print_status(f"Failed to get bug number: {bug_result.stderr}", "error")
            return False
        bug = bug_result.stdout.strip()
        print_status(f"Bug number: {bug}", "info")

        # Get workspace name for agent-based generation
        ws_result = run_shell_command("workspace_name", capture_output=True)
        if ws_result.returncode != 0:
            print_status(f"Failed to get workspace name: {ws_result.stderr}", "error")
            return False
        workspace_name = ws_result.stdout.strip()

        # Claim workspace in project file's RUNNING field
        project_file, workspace_num, workspace_dir = (
            get_project_file_and_workspace_info(workspace_name)
        )
        if project_file and workspace_num:
            claim_success = claim_workspace(
                project_file, workspace_num, "split", cl_name
            )
            if not claim_success:
                print_status("Failed to claim workspace", "error")
                return False
            if workspace_num > 1:
                print_status(
                    f"Using workspace share: {workspace_name}_{workspace_num}",
                    "info",
                )

        try:
            return self._run_split_workflow(
                cl_name=cl_name,
                console=console,
                workflow_tag=workflow_tag,
                timestamp=timestamp,
                diff_path=diff_path,
                bug=bug,
                workspace_name=workspace_name,
            )
        finally:
            # Always release the workspace when done
            if project_file and workspace_num:
                release_workspace(project_file, workspace_num, "split", cl_name)

    def _run_split_workflow(
        self,
        cl_name: str,
        console: Console,
        workflow_tag: str,
        timestamp: str,
        diff_path: str,
        bug: str,
        workspace_name: str,
    ) -> bool:
        """Execute the main split workflow logic.

        This is extracted to enable proper try/finally workspace cleanup.

        Returns:
            True if successful, False otherwise.
        """
        # Get default_parent from ChangeSpec's PARENT field (or "p4head" if none)
        all_cs = find_all_changespecs()
        target_cs = next((cs for cs in all_cs if cs.name == cl_name), None)
        if target_cs and target_cs.parent:
            default_parent = target_cs.parent
        else:
            default_parent = "p4head"
        print_status(f"Default parent: {default_parent}", "info")

        # Create artifacts directory early (needed for agent-based generation)
        artifacts_dir = create_artifacts_directory("split")
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")

        # Initialize the gai.md log
        initialize_gai_log(artifacts_dir, "split", workflow_tag)

        # Step 5: Handle spec file (create/edit, load existing, or generate)
        print_status("Handling split specification...", "progress")
        if self._generate_spec:
            # Use agent to generate spec
            result = generate_spec_with_agent(
                cl_name=cl_name,
                workspace_name=workspace_name,
                diff_path=diff_path,
                timestamp=timestamp,
                console=console,
                artifacts_dir=artifacts_dir,
                workflow_tag=workflow_tag,
            )
            if result is None:
                print_status("Spec generation aborted by user.", "error")
                return False
            spec_content, archive_path = result
        elif self._create_spec:
            # Create new spec and edit
            result = create_and_edit_spec(cl_name, timestamp)
            if result is None:
                print_status(
                    "No valid split specification provided. Aborting.", "error"
                )
                return False
            spec_content, archive_path = result
        elif self._spec_path:
            # Load existing spec
            if not os.path.isfile(self._spec_path):
                print_status(f"Spec file not found: {self._spec_path}", "error")
                return False
            spec_content, archive_path = load_and_archive_spec(
                cl_name, self._spec_path, timestamp
            )
        else:
            print_status("No spec file provided. Use -s option.", "error")
            return False

        # Parse and validate the spec
        try:
            spec = parse_split_spec(spec_content)
        except ValueError as e:
            print_status(f"Invalid split spec: {e}", "error")
            return False

        is_valid, error_msg = validate_split_spec(spec)
        if not is_valid:
            print_status(f"Invalid split spec: {error_msg}", "error")
            return False

        print_status(f"Spec archived to: {archive_path}", "success")
        print_status(
            f"Split will create {len(spec.entries)} new CL(s).",
            "info",
        )

        # Navigate to parent
        print_status(f"Navigating to parent: {default_parent}...", "progress")
        parent_nav_result = run_shell_command(
            f"bb_hg_update {default_parent}", capture_output=True
        )
        if parent_nav_result.returncode != 0:
            print_status(
                f"Warning: Failed to navigate to parent: {parent_nav_result.stderr}",
                "warning",
            )
        else:
            print_status(f"Now on parent: {default_parent}", "success")

        # Step 6: Build and invoke Gemini agent
        print_status("Building split prompt...", "progress")
        prompt = build_split_prompt(
            diff_path=diff_path,
            spec=spec,
            default_parent=default_parent,
            bug=bug,
            original_name=cl_name,
            spec_archive_path=archive_path,
        )

        # Save prompt to artifacts
        prompt_path = os.path.join(artifacts_dir, "split_prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print_status(f"Prompt saved to: {prompt_path}", "info")

        print_status("Invoking Gemini agent to perform split...", "progress")
        model = GeminiCommandWrapper(model_size="big")
        model.set_logging_context(
            agent_type="split",
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
            workflow="split",
        )

        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = model.invoke(messages)

        # Save the response
        response_path = os.path.join(artifacts_dir, "split_response.txt")
        with open(response_path, "w", encoding="utf-8") as f:
            f.write(ensure_str_content(response.content))
        print_status(f"Response saved to: {response_path}", "success")

        print_status("Split agent completed!", "success")

        # Finalize the gai.md log
        finalize_gai_log(artifacts_dir, "split", workflow_tag, True)

        # Step 7: Prompt user to revert original CL
        prompt_for_revert(cl_name, console)

        return True
