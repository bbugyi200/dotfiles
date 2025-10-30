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


def extract_test_command_from_artifacts(artifacts_dir: str) -> str:
    """Extract the test command from agent response artifacts."""
    # Look for the test command in agent response files
    try:
        for file in os.listdir(artifacts_dir):
            if file.startswith("agent_") and file.endswith("_response.txt"):
                artifact_path = os.path.join(artifacts_dir, file)
                content = read_artifact_file(artifact_path)
                # Look for test command pattern in the response
                lines = content.split("\n")
                for line in lines:
                    if "Test command:" in line:
                        return line.split("Test command:", 1)[1].strip()
    except Exception:
        pass

    # Fallback: try to find it in other artifacts
    try:
        # Check if there's a summary file or other artifacts that might contain it
        for filename in ["test_output.txt", "cl_description.txt"]:
            artifact_path = os.path.join(artifacts_dir, filename)
            if os.path.exists(artifact_path):
                content = read_artifact_file(artifact_path)
                if content.strip().startswith("#"):
                    # First line might be the test command
                    first_line = content.split("\n")[0]
                    if first_line.startswith("# "):
                        return first_line[2:].strip()
    except Exception:
        pass

    return "Unknown test command"


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


def collect_all_artifacts(artifacts_dir: str, exclude_full_outputs: bool = True) -> str:
    """
    Collect ALL artifacts from the artifacts directory, excluding test_full_output files.
    Provides file paths and descriptions for all artifacts instead of full contents.

    Args:
        artifacts_dir: Directory containing artifacts
        exclude_full_outputs: If True, exclude *test_full_output.txt files (default: True)

    Returns:
        String containing artifact file paths and descriptions with clear section headers
    """
    artifacts_summary = ""

    if not os.path.exists(artifacts_dir):
        return f"Error: Artifacts directory '{artifacts_dir}' does not exist"

    def get_file_description(filename: str) -> str:
        """Get a helpful description for a file based on its name."""
        # Initial artifacts
        if filename == "test_output.txt":
            return "Test failure output and error messages"
        elif filename == "cl_description.txt":
            return "Change list description from hdesc command"
        elif filename in ["cl_diff.txt", "current_diff.txt"]:
            return "Code changes and diffs"

        # Agent artifacts
        elif filename.startswith("agent_") and filename.endswith("_response.txt"):
            agent_num = filename.split("_")[1]
            return f"Response and analysis from Agent {agent_num}"
        elif filename.startswith("agent_") and (
            "changes" in filename or filename.endswith(".diff")
        ):
            agent_num = filename.split("_")[1]
            return f"Code changes made by Agent {agent_num}"
        elif filename.startswith("agent_") and "test_failure" in filename:
            agent_num = filename.split("_")[1]
            return f"Test failure output after Agent {agent_num}'s changes"
        elif filename.startswith("agent_") and "test_summary" in filename:
            agent_num = filename.split("_")[1]
            return f"Test execution summary for Agent {agent_num}"
        elif filename.startswith("agent_") and "build_cleaner" in filename:
            agent_num = filename.split("_")[1]
            return f"Build cleaner output for Agent {agent_num}"

        # GAI test artifacts
        elif filename.endswith("_output.txt") and not filename.startswith("agent_"):
            return "Test execution output from gai_test"
        elif filename.endswith(".diff") and "test_diffs" not in filename:
            return "Code changes diff"
        elif "test_runs_limit" in filename:
            return "Test run limit configuration"
        elif "agent_test_counts" in filename:
            return "Agent test execution counts"

        # Research artifacts
        elif "research_summary" in filename:
            if "cycle_" in filename:
                cycle_num = filename.split("cycle_")[1].split(".")[0]
                return f"Research findings and insights from cycle {cycle_num}"
            return "Research findings and insights"
        elif "research_resources" in filename:
            if "cycle_" in filename:
                cycle_num = filename.split("cycle_")[1].split(".")[0]
                return f"Resources and references discovered in cycle {cycle_num}"
            return "Resources and references discovered during research"

        # Other files
        elif filename.endswith(".md"):
            return "Markdown document with detailed information"
        elif filename.endswith(".diff") or "_diff" in filename:
            return "Code changes and diffs"
        elif "output" in filename:
            return "Command output or execution results"
        else:
            return "Artifact file"

    def add_file_reference(file: str, file_path: str, artifacts_summary: str) -> str:
        """Add file path and description for an artifact."""
        description = get_file_description(file)
        artifacts_summary += f"\n--- {file} ---\n"
        artifacts_summary += f"Path: {file_path}\n"
        artifacts_summary += f"Description: {description}\n"
        return artifacts_summary

    try:
        # Get all files in the artifacts directory
        all_files = []
        for file in os.listdir(artifacts_dir):
            file_path = os.path.join(artifacts_dir, file)
            if os.path.isfile(file_path):
                # Skip test_full_output files if requested
                if exclude_full_outputs and "test_full_output" in file:
                    continue
                all_files.append(file)

        # Sort files for consistent ordering
        all_files.sort()

        # Group files by type for better organization
        initial_artifacts = []
        agent_artifacts = []
        research_artifacts = []

        for file in all_files:
            if file in [
                "test_output.txt",
                "cl_description.txt",
                "cl_diff.txt",
                "current_diff.txt",
            ]:
                initial_artifacts.append(file)
            elif file.startswith("agent_") and file.endswith(
                ("_response.txt", ".diff", "_test_summary.txt")
            ):
                agent_artifacts.append(file)
            elif "research" in file:
                research_artifacts.append(file)

        # Add initial artifacts first
        if initial_artifacts:
            artifacts_summary += create_boxed_header("INITIAL ARTIFACTS")
            for file in initial_artifacts:
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

        # Add research artifacts
        if research_artifacts:
            artifacts_summary += create_boxed_header("RESEARCH ARTIFACTS")
            for file in sorted(research_artifacts):
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

        # Add agent artifacts
        if agent_artifacts:
            artifacts_summary += create_boxed_header("AGENT ARTIFACTS")
            for file in sorted(agent_artifacts):
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )
    except Exception as e:
        artifacts_summary += f"\nError collecting artifacts: {str(e)}\n"

    return artifacts_summary


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


def get_gai_log_file() -> str:
    """Get the path to the central gai.md log file."""
    # Use the same bb/gai directory structure
    gai_dir = "bb/gai"
    Path(gai_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(gai_dir, "gai.md")


def log_prompt_and_response(
    prompt: str,
    response: str,
    agent_type: str = "agent",
    iteration: int = None,
    workflow_tag: str = None,
) -> None:
    """
    Log a prompt and response to the central gai.md file.

    Args:
        prompt: The prompt sent to the AI
        response: The response received from the AI
        agent_type: Type of agent (e.g., "editor", "planner", "research", "verification")
        iteration: Iteration number if applicable
        workflow_tag: Workflow tag if available
    """
    try:
        log_file = get_gai_log_file()
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


def initialize_gai_log(workflow_name: str, workflow_tag: str) -> None:
    """
    Initialize the gai.md log file for a new workflow run.

    Args:
        workflow_name: Name of the workflow (e.g., "fix-tests", "add-tests")
        workflow_tag: Unique workflow tag
    """
    try:
        log_file = get_gai_log_file()
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        # Create initialization entry
        init_entry = f"""
# GAI Workflow Log - {workflow_name} ({workflow_tag})

Started: {timestamp}

"""

        # If file doesn't exist, create it. If it does, append new workflow section
        if not os.path.exists(log_file):
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(init_entry)
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(init_entry)

    except Exception as e:
        print(f"Warning: Failed to initialize gai.md log: {e}")


def finalize_gai_log(workflow_name: str, workflow_tag: str, success: bool) -> None:
    """
    Finalize the gai.md log file for a completed workflow run.

    Args:
        workflow_name: Name of the workflow
        workflow_tag: Unique workflow tag
        success: Whether the workflow completed successfully
    """
    try:
        log_file = get_gai_log_file()
        eastern = ZoneInfo("America/New_York")
        timestamp = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S EST")

        status = "SUCCESS" if success else "FAILED"

        final_entry = f"""
## Workflow Completed - {timestamp}

**Status:** {status}  
**Workflow:** {workflow_name}  
**Tag:** {workflow_tag}

===============================================================================

"""

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(final_entry)

    except Exception as e:
        print(f"Warning: Failed to finalize gai.md log: {e}")
