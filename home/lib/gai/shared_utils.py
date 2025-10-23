import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


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
    """Create a timestamped artifacts directory using EST timezone."""
    est = ZoneInfo("US/Eastern")
    timestamp = datetime.now(est).strftime("%Y%m%d%H%M%S")
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
        filename_lower = filename.lower()

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
        other_artifacts = []

        for file in all_files:
            if file in [
                "test_output.txt",
                "cl_description.txt",
                "cl_diff.txt",
                "current_diff.txt",
            ]:
                initial_artifacts.append(file)
            elif file.startswith("agent_"):
                agent_artifacts.append(file)
            elif "research" in file:
                research_artifacts.append(file)
            else:
                other_artifacts.append(file)

        # Add initial artifacts first
        if initial_artifacts:
            artifacts_summary += "\n=== INITIAL ARTIFACTS ===\n"
            for file in initial_artifacts:
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

        # Add research artifacts
        if research_artifacts:
            artifacts_summary += "\n=== RESEARCH ARTIFACTS ===\n"
            for file in sorted(research_artifacts):
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

        # Add agent artifacts
        if agent_artifacts:
            artifacts_summary += "\n=== AGENT ARTIFACTS ===\n"
            for file in sorted(agent_artifacts):
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

        # Add other artifacts
        if other_artifacts:
            artifacts_summary += "\n=== OTHER ARTIFACTS ===\n"
            for file in sorted(other_artifacts):
                file_path = os.path.join(artifacts_dir, file)
                artifacts_summary = add_file_reference(
                    file, file_path, artifacts_summary
                )

    except Exception as e:
        artifacts_summary += f"\nError collecting artifacts: {str(e)}\n"

    return artifacts_summary


def run_bam_command(message: str) -> None:
    """Run bam command to signal completion."""
    try:
        run_shell_command(f'bam 3 0.1 "{message}"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")
