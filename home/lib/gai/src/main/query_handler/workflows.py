"""Workflow dispatch for gai run subcommands."""

import argparse
import os
import sys
from typing import NoReturn

from crs_workflow import CrsWorkflow
from mentor_workflow import MentorWorkflow
from shared_utils import run_shell_command
from workflow_base import BaseWorkflow


def handle_run_workflows(args: argparse.Namespace) -> NoReturn:
    """Handle run workflow subcommands.

    Args:
        args: Parsed command-line arguments.
    """
    workflow: BaseWorkflow

    if args.workflow == "crs":
        # Determine project_name from workspace_name command
        try:
            result = run_shell_command("workspace_name", capture_output=True)
            if result.returncode == 0:
                project_name = result.stdout.strip()
            else:
                print(
                    "Error: Could not determine project name from workspace_name command"
                )
                print(f"workspace_name failed: {result.stderr}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: Could not run workspace_name command: {e}")
            sys.exit(1)

        # Determine context_file_directory (default to ~/.gai/projects/<project>/context/)
        context_file_directory = args.context_file_directory
        if not context_file_directory:
            context_file_directory = os.path.expanduser(
                f"~/.gai/projects/{project_name}/context/"
            )

        workflow = CrsWorkflow(context_file_directory=context_file_directory)
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "fix-hook":
        from fix_hook_workflow import FixHookWorkflow

        workflow = FixHookWorkflow(
            hook_output_file=args.hook_output_file,
            hook_command=args.hook_command,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "mentor":
        # Parse profile:mentor format
        if ":" not in args.mentor_spec:
            print(
                f"Error: mentor_spec must be in format 'profile:mentor', "
                f"got '{args.mentor_spec}'",
                file=sys.stderr,
            )
            sys.exit(1)
        profile_name, mentor_name = args.mentor_spec.split(":", 1)

        workflow = MentorWorkflow(
            profile_name=profile_name,
            mentor_name=mentor_name,
            cl_name=args.cl_name,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "split":
        from ace.split_workflow import SplitWorkflow

        # Determine spec handling mode
        if args.spec is None:
            # No -s option: use agent to generate spec
            spec_path = None
            create_spec = False
            generate_spec = True
        elif args.spec == "":
            # -s without argument: create new spec in editor
            spec_path = None
            create_spec = True
            generate_spec = False
        else:
            # -s with path: load existing spec
            spec_path = args.spec
            create_spec = False
            generate_spec = False

        workflow = SplitWorkflow(
            name=args.name,
            spec_path=spec_path,
            create_spec=create_spec,
            generate_spec=generate_spec,
            yolo=args.yolo,
        )
        success = workflow.run()
        sys.exit(0 if success else 1)
    elif args.workflow == "summarize":
        from summarize_workflow import SummarizeWorkflow

        workflow = SummarizeWorkflow(
            target_file=args.target_file,
            usage=args.usage,
        )
        success = workflow.run()
        if success and workflow.summary:
            print(workflow.summary)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)
