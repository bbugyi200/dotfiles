"""
LangGraph tools for API-based Gemini agents to perform file operations and shell commands.
"""

import os
import subprocess
from typing import Dict, Any
from langchain_core.tools import tool


@tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file, creating directories as needed.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file

    Returns:
        Success or error message
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"


@tool
def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        File contents or error message
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"


@tool
def edit_file(file_path: str, old_content: str, new_content: str) -> str:
    """
    Edit a file by replacing old_content with new_content.

    Args:
        file_path: Path to the file to edit
        old_content: Content to replace
        new_content: New content to insert

    Returns:
        Success or error message
    """
    try:
        # Read current file content
        with open(file_path, "r", encoding="utf-8") as f:
            current_content = f.read()

        # Replace content
        if old_content in current_content:
            updated_content = current_content.replace(old_content, new_content)

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return f"Successfully edited {file_path}"
        else:
            return f"Error: old_content not found in {file_path}"

    except Exception as e:
        return f"Error editing {file_path}: {str(e)}"


@tool
def append_to_file(file_path: str, content: str) -> str:
    """
    Append content to a file.

    Args:
        file_path: Path to the file to append to
        content: Content to append

    Returns:
        Success or error message
    """
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully appended to {file_path}"
    except Exception as e:
        return f"Error appending to {file_path}: {str(e)}"


@tool
def run_shell_command(command: str, working_directory: str = None) -> str:
    """
    Execute a shell command and return the output.

    Args:
        command: Shell command to execute
        working_directory: Optional working directory for the command

    Returns:
        Command output or error message
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_directory,
            timeout=30,  # 30 second timeout for safety
        )

        output = f"Command: {command}\n"
        output += f"Return code: {result.returncode}\n"

        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"

        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after 30 seconds"
    except Exception as e:
        return f"Error running command '{command}': {str(e)}"


@tool
def list_directory(directory_path: str) -> str:
    """
    List the contents of a directory.

    Args:
        directory_path: Path to the directory to list

    Returns:
        Directory contents or error message
    """
    try:
        if not os.path.exists(directory_path):
            return f"Error: Directory {directory_path} does not exist"

        if not os.path.isdir(directory_path):
            return f"Error: {directory_path} is not a directory"

        contents = os.listdir(directory_path)
        contents.sort()

        result = f"Contents of {directory_path}:\n"
        for item in contents:
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                result += f"  📁 {item}/\n"
            else:
                result += f"  📄 {item}\n"

        return result

    except Exception as e:
        return f"Error listing directory {directory_path}: {str(e)}"


@tool
def file_exists(file_path: str) -> str:
    """
    Check if a file or directory exists.

    Args:
        file_path: Path to check

    Returns:
        Existence status message
    """
    try:
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                return f"File {file_path} exists"
            elif os.path.isdir(file_path):
                return f"Directory {file_path} exists"
            else:
                return f"Path {file_path} exists but is neither file nor directory"
        else:
            return f"Path {file_path} does not exist"
    except Exception as e:
        return f"Error checking {file_path}: {str(e)}"


# Available tools for the API agents
AVAILABLE_TOOLS = [
    write_file,
    read_file,
    edit_file,
    append_to_file,
    run_shell_command,
    list_directory,
    file_exists,
]


def get_tools_by_name() -> Dict[str, Any]:
    """Get a dictionary mapping tool names to tool objects."""
    return {tool.name: tool for tool in AVAILABLE_TOOLS}
