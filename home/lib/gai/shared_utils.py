import os
import random
import string
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# LangGraph configuration
LANGGRAPH_RECURSION_LIMIT = 100


def run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


def run_shell_command_with_input(
    cmd: str, input_text: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command with input text and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        input=input_text,
        capture_output=capture_output,
        text=True,
    )


def read_artifact_file(file_path: str) -> str:
    """Read the contents of an artifact file."""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"



def create_artifacts_directory() -> str:
    """Create a timestamped artifacts directory using NYC Eastern timezone."""
    eastern = ZoneInfo("America/New_York")
    timestamp = datetime.now(eastern).strftime("%Y%m%d%H%M%S")
    artifacts_dir = f"bb/gai/{timestamp}"
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def create_hdesc_artifact(artifacts_dir: str) -> str:
    """Create artifact with hdesc output."""
    result = run_shell_command("hdesc")

    artifact_path = os.path.join(artifacts_dir, "cl_description.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def create_diff_artifact(artifacts_dir: str) -> str:
    """Create artifact with hg pdiff output."""
    cmd = "hg pdiff $(branch_changes | grep -v -E 'png$|fingerprint$|BUILD$|recordio$')"
    result = run_shell_command(cmd)

    artifact_path = os.path.join(artifacts_dir, "cl_diff.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def create_boxed_header(title: str) -> str:
    """Create a pretty boxed header with equal signs."""
    # Add padding around the title
    padded_title = f" {title} "
    box_width = len(padded_title) + 2

    # Create the box
    top_bottom = "=" * box_width
    middle = f"={padded_title}="

    return f"\n{top_bottom}\n{middle}\n{top_bottom}"




def has_uncommitted_changes() -> bool:
    """Check if there are any uncommitted changes using hg diff."""
    try:
        result = run_shell_command("hg diff", capture_output=True)
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Warning: Failed to check for uncommitted changes: {e}")
        return False


def safe_hg_amend(commit_message: str, use_unamend_first: bool = False) -> bool:
    """
    Safely run hg amend with proper error handling and safeguards.

    Args:
        commit_message: The commit message to use
        use_unamend_first: Whether to run unamend before amend (for subsequent amends)

    Returns:
        bool: True if successful, False if failed
    """
    # Check if there are any uncommitted changes
    if not has_uncommitted_changes():
        print("⚠️ No uncommitted changes detected - skipping hg amend")
        return True  # Not an error condition, just nothing to commit

    try:
        if use_unamend_first:
            # First run unamend
            print("Running hg unamend before amend...")
            unamend_result = run_shell_command("hg unamend", capture_output=True)
            if unamend_result.returncode != 0:
                print(f"❌ hg unamend failed: {unamend_result.stderr}")
                return False
            print("✅ hg unamend successful")

        # Run the amend command
        amend_cmd = f"hg amend -n '{commit_message}'"
        print(f"Running: {amend_cmd}")
        amend_result = run_shell_command(amend_cmd, capture_output=True)

        if amend_result.returncode == 0:
            print(f"✅ hg amend successful: {commit_message}")
            return True
        else:
            print(f"❌ hg amend failed: {amend_result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error during hg amend operation: {e}")
        return False


def generate_workflow_tag() -> str:
    """Generate a unique 3-digit alphanumeric tag for the workflow run."""
    # Use digits and uppercase letters for better readability
    chars = string.digits + string.ascii_uppercase
    return "".join(random.choices(chars, k=3))


def run_bam_command(message: str) -> None:
    """Run bam command to signal completion."""
    try:
        run_shell_command(f'bam 3 0.1 "{message}"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")


def get_gai_log_file(artifacts_dir: str) -> str:
    """Get the path to the workflow-specific gai.md log file."""
    return os.path.join(artifacts_dir, "gai.md")


def log_prompt_and_response(
    prompt: str,
    response: str,
    artifacts_dir: str,
    agent_type: str = "agent",
    iteration: int = None,
    workflow_tag: str = None,
) -> None:
    """
    Log a prompt and response to the workflow-specific gai.md file.

    Args:
        prompt: The prompt sent to the AI
        response: The response received from the AI
        artifacts_dir: Directory where the gai.md file should be stored
        agent_type: Type of agent (e.g., "editor", "planner", "research", "verification")
        iteration: Iteration number if applicable
        workflow_tag: Workflow tag if available
    """
    try:
        log_file = get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create header for this entry
        header_parts = [agent_type]
        if iteration is not None:
            header_parts.append(f"iteration {iteration}")
        if workflow_tag:
            header_parts.append(f"tag {workflow_tag}")

        header = " - ".join(header_parts)

        # Format the log entry
        log_entry = f"""
## {timestamp} - {header}

### PROMPT:
```
{prompt}
```

### RESPONSE:
```
{response}
```

---

"""

        # Append to the log file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except Exception as e:
        print(f"Warning: Failed to log prompt and response to gai.md: {e}")


def initialize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str
) -> None:
    """
    Initialize the gai.md log file for a new workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file should be stored
        workflow_name: Name of the workflow (e.g., "fix-tests", "add-tests")
        workflow_tag: Unique workflow tag
    """
    try:
        log_file = get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create initialization entry
        init_entry = f"""# GAI Workflow Log - {workflow_name} ({workflow_tag})

Started: {timestamp}
Artifacts Directory: {artifacts_dir}

"""

        # Create the file (should be new for each workflow run)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(init_entry)

        print(f"✅ Initialized GAI log: {log_file}")

    except Exception as e:
        print(f"Warning: Failed to initialize gai.md log: {e}")


def finalize_gai_log(
    artifacts_dir: str, workflow_name: str, workflow_tag: str, success: bool
) -> None:
    """
    Finalize the gai.md log file for a completed workflow run.

    Args:
        artifacts_dir: Directory where the gai.md file is stored
        workflow_name: Name of the workflow
        workflow_tag: Unique workflow tag
        success: Whether the workflow completed successfully
    """
    try:
        log_file = get_gai_log_file(artifacts_dir)
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        status = "SUCCESS" if success else "FAILED"

        final_entry = f"""
## Workflow Completed - {timestamp}

**Status:** {status}  
**Workflow:** {workflow_name}  
**Tag:** {workflow_tag}  
**Artifacts Directory:** {artifacts_dir}

===============================================================================

"""

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(final_entry)

        print(f"✅ Finalized GAI log: {log_file}")

    except Exception as e:
        print(f"Warning: Failed to finalize gai.md log: {e}")
