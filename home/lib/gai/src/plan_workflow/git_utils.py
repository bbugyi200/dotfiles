"""Git utilities for the plan workflow."""

import subprocess
from pathlib import Path

GAI_DIR = Path.home() / ".gai"
PLANS_DIR = GAI_DIR / "plans"


def _ensure_gai_git_repo() -> None:
    """Ensure ~/.gai is a git repository."""
    git_dir = GAI_DIR / ".git"
    if not git_dir.exists():
        subprocess.run(
            ["git", "init"],
            cwd=str(GAI_DIR),
            capture_output=True,
            check=True,
        )


def ensure_plans_directory() -> Path:
    """Ensure the plans directory exists and return its path."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    return PLANS_DIR


def commit_plan(plan_path: str, commit_message: str) -> None:
    """Stage and commit changes to the plan file in ~/.gai git repo.

    Args:
        plan_path: Absolute path to the plan file.
        commit_message: Git commit message.
    """
    # Verify the file is inside ~/.gai
    try:
        plan_path_resolved = Path(plan_path).resolve()
        gai_path = GAI_DIR.resolve()
        if not str(plan_path_resolved).startswith(str(gai_path)):
            return
    except (OSError, ValueError):
        return

    _ensure_gai_git_repo()

    # Stage the specific file
    subprocess.run(
        ["git", "add", plan_path],
        cwd=str(GAI_DIR),
        capture_output=True,
        check=True,
    )

    # Commit (don't fail if nothing to commit)
    subprocess.run(
        ["git", "commit", "-m", commit_message, "--", plan_path],
        cwd=str(GAI_DIR),
        capture_output=True,
        check=False,
    )
