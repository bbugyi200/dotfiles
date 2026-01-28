"""Workflow dispatch for gai run subcommands."""

import argparse
import sys
from typing import NoReturn

from workflow_base import BaseWorkflow


def handle_run_workflows(args: argparse.Namespace) -> NoReturn:
    """Handle run workflow subcommands.

    Args:
        args: Parsed command-line arguments.
    """
    workflow: BaseWorkflow

    if args.workflow == "split":
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
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)
