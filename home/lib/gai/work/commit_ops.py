"""Commit-related operations for ChangeSpecs."""

import subprocess

from rich.console import Console


def run_bb_hg_upload(target_dir: str, console: Console) -> tuple[bool, str | None]:
    """Run bb_hg_upload to upload changes to Critique.

    Args:
        target_dir: Directory to run the command in
        console: Rich Console object for status output

    Returns:
        Tuple of (success, error_message)
    """
    console.print("[cyan]Uploading to Critique...[/cyan]")
    try:
        subprocess.run(
            ["bb_hg_upload"],
            cwd=target_dir,
            check=True,
        )
        console.print("[green]Upload completed successfully![/green]")
        return (True, None)
    except subprocess.CalledProcessError as e:
        return (False, f"bb_hg_upload failed (exit code {e.returncode})")
    except FileNotFoundError:
        return (False, "bb_hg_upload command not found")
    except Exception as e:
        return (False, f"Unexpected error running bb_hg_upload: {str(e)}")
