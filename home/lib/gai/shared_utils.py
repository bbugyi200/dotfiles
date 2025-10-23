import os
import subprocess
from datetime import datetime
from pathlib import Path


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
    """Create a timestamped artifacts directory."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
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
    cmd = "hg pdiff $(branch_changes | grep -v -E 'png$|fingerprint$|BUILD$')"
    result = run_shell_command(cmd)

    artifact_path = os.path.join(artifacts_dir, "cl_diff.txt")
    with open(artifact_path, "w") as f:
        f.write(result.stdout)

    return artifact_path


def run_bam_command(message: str) -> None:
    """Run bam command to signal completion."""
    try:
        run_shell_command(f'bam 3 0.1 "{message}"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")
