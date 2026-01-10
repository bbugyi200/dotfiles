"""Main entry point for the GAI CLI tool."""

import sys
from typing import NoReturn

from ace.query import QueryParseError

from .cl_handler import (
    handle_amend_command,
    handle_commit_command,
    handle_restore_command,
    handle_revert_command,
)
from .parser import create_parser
from .query_handler import handle_run_special_cases, handle_run_workflows


def main() -> NoReturn:
    """Main entry point for the GAI CLI tool."""
    # Check for 'gai run' special cases before argparse processes it
    # This allows us to handle queries that contain spaces
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        args_after_run = sys.argv[2:]
        handle_run_special_cases(args_after_run)
        # If we get here, no special case was handled, continue to argparse

    parser = create_parser()
    args = parser.parse_args()

    # =========================================================================
    # COMMAND HANDLERS (keep sorted alphabetically to match parser order)
    # =========================================================================

    # --- amend ---
    if args.command == "amend":
        handle_amend_command(args)

    # --- commit ---
    if args.command == "commit":
        handle_commit_command(args)

    # --- loop ---
    if args.command == "loop":
        from ace.loop import LoopWorkflow

        try:
            loop_workflow = LoopWorkflow(
                interval_seconds=args.interval,
                verbose=args.verbose,
                hook_interval_seconds=args.hook_interval,
                zombie_timeout_seconds=args.zombie_timeout,
                max_runners=args.max_runners,
                query=args.query,
            )
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)
        success = loop_workflow.run()
        sys.exit(0 if success else 1)

    # --- restore ---
    if args.command == "restore":
        handle_restore_command(args)

    # --- search ---
    if args.command == "search":
        from pathlib import Path

        from ace.changespec import find_all_changespecs
        from ace.display import display_changespec
        from ace.query import evaluate_query, parse_query
        from rich.console import Console

        try:
            parsed_query = parse_query(args.query)
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)

        all_changespecs = find_all_changespecs()
        matching = [
            cs
            for cs in all_changespecs
            if evaluate_query(parsed_query, cs, all_changespecs)
        ]

        if not matching:
            print("No ChangeSpecs match the query.")
            sys.exit(0)

        if args.format == "rich":
            from collections import Counter

            from ace.display_helpers import get_status_color
            from rich.panel import Panel
            from rich.text import Text

            console = Console()
            for cs in matching:
                display_changespec(cs, console)

            # Print summary panel
            summary = Text()

            # Count and status breakdown
            status_counts = Counter(cs.status for cs in matching)
            breakdown = ", ".join(
                f"{count} {status}" for status, count in sorted(status_counts.items())
            )
            summary.append(
                f"Found {len(matching)} ChangeSpec(s): {breakdown}\n\n", style="bold"
            )

            # One-line per ChangeSpec
            for cs in matching:
                status_color = get_status_color(cs.status)
                summary.append(f"  {cs.name}", style="bold #00D7AF")
                summary.append(f" [{cs.status}]\n", style=f"bold {status_color}")

            summary.rstrip()
            console.print(Panel(summary, title="Summary", border_style="green"))
        else:
            # Plain format: full ChangeSpec details without colors
            from ace.display_helpers import (
                format_running_claims_aligned,
                get_bug_field,
            )
            from ace.hooks import format_timestamp_display
            from running_field import get_claimed_workspaces

            for cs in matching:
                file_path = cs.file_path.replace(str(Path.home()), "~")
                print(f"--- {file_path}:{cs.line_number} ---")

                # BUG field (from ProjectSpec)
                bug_field = get_bug_field(cs.file_path)
                if bug_field:
                    print(f"BUG: {bug_field}")

                # RUNNING field (from ProjectSpec)
                running_claims = get_claimed_workspaces(cs.file_path)
                if running_claims:
                    print("RUNNING:")
                    formatted_claims = format_running_claims_aligned(running_claims)
                    for ws_col, wf_col, cl_name in formatted_claims:
                        if cl_name:
                            print(f"  {ws_col} | {wf_col} | {cl_name}")
                        else:
                            print(f"  {ws_col} | {wf_col}")

                print(f"NAME: {cs.name}")
                print("DESCRIPTION:")
                for line in cs.description.split("\n"):
                    print(f"  {line}")
                if cs.kickstart:
                    print("KICKSTART:")
                    for line in cs.kickstart.split("\n"):
                        print(f"  {line}")
                if cs.parent:
                    print(f"PARENT: {cs.parent}")
                if cs.cl:
                    print(f"CL: {cs.cl}")
                print(f"STATUS: {cs.status}")
                if cs.test_targets:
                    targets = [t for t in cs.test_targets if t != "None"]
                    if targets:
                        print(f"TEST TARGETS: {', '.join(targets)}")
                if cs.commits:
                    print("COMMITS:")
                    for entry in cs.commits:
                        suffix_str = f" - ({entry.suffix})" if entry.suffix else ""
                        print(f"  ({entry.display_number}) {entry.note}{suffix_str}")
                        if entry.chat:
                            chat_path = entry.chat.replace(str(Path.home()), "~")
                            print(f"      | CHAT: {chat_path}")
                        if entry.diff:
                            diff_path = entry.diff.replace(str(Path.home()), "~")
                            print(f"      | DIFF: {diff_path}")
                if cs.hooks:
                    print("HOOKS:")
                    for hook in cs.hooks:
                        print(f"  {hook.command}")
                        for sl in hook.status_lines or []:
                            suffix_str = f" - ({sl.suffix})" if sl.suffix else ""
                            duration_str = f" ({sl.duration})" if sl.duration else ""
                            ts_str = format_timestamp_display(sl.timestamp)
                            print(
                                f"      | ({sl.commit_entry_num}) [{ts_str}] {sl.status}"
                                f"{duration_str}{suffix_str}"
                            )
                if cs.comments:
                    print("COMMENTS:")
                    for comment in cs.comments:
                        suffix_str = f" - ({comment.suffix})" if comment.suffix else ""
                        comment_path = comment.file_path.replace(str(Path.home()), "~")
                        print(f"  [{comment.reviewer}] {comment_path}{suffix_str}")
                if cs.mentors:
                    print("MENTORS:")
                    for mentor in cs.mentors:
                        profiles_str = " ".join(mentor.profiles)
                        print(f"  ({mentor.entry_id}) {profiles_str}")
                        # Print status lines for each mentor entry
                        if mentor.status_lines:
                            for msl in mentor.status_lines:
                                ts_str = (
                                    f"[{format_timestamp_display(msl.timestamp)}] "
                                    if msl.timestamp
                                    else ""
                                )
                                duration_str = (
                                    f" - ({msl.duration})" if msl.duration else ""
                                )
                                suffix_str = f" - ({msl.suffix})" if msl.suffix else ""
                                print(
                                    f"      | {ts_str}{msl.profile_name}:{msl.mentor_name}"
                                    f" - {msl.status}{duration_str}{suffix_str}"
                                )
                print()  # Blank line between ChangeSpecs

        sys.exit(0)

    # --- revert ---
    if args.command == "revert":
        handle_revert_command(args)

    # --- ace ---
    if args.command == "ace":
        from ace.tui import AceApp

        try:
            app = AceApp(
                query=args.query,
                model_size_override=getattr(args, "model_size", None),
                refresh_interval=args.refresh_interval,
            )
        except QueryParseError as e:
            print(f"Error: Invalid query: {e}")
            sys.exit(1)
        app.run()
        sys.exit(0)

    # --- xprompt ---
    if args.command == "xprompt":
        from gemini_wrapper import (
            format_with_prettier,
            process_command_substitution,
            process_snippet_references,
            process_xcmd_references,
            validate_file_references,
        )

        prompt = args.prompt if args.prompt else sys.stdin.read()
        prompt = process_snippet_references(prompt)
        prompt = process_command_substitution(prompt)
        prompt = process_xcmd_references(prompt)
        validate_file_references(prompt)  # Validates but doesn't modify
        print(format_with_prettier(prompt), end="")
        sys.exit(0)

    # --- run workflows ---
    if args.command != "run":
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    # Workflow handlers under 'run'
    handle_run_workflows(args)


if __name__ == "__main__":
    main()
