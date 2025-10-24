import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class BlackboardManager:
    """Manages blackboard files for the fix-tests workflow."""

    def __init__(self, blackboard_dir: str):
        self.blackboard_dir = blackboard_dir
        self.planning_blackboard_pattern = "planning_blackboard_*.md"
        self.editor_blackboard_file = "editor_blackboard.md"
        self.research_blackboard_file = "research_blackboard.md"

        # Ensure blackboard directory exists
        Path(self.blackboard_dir).mkdir(parents=True, exist_ok=True)

    def get_planning_blackboard_path(self) -> str:
        """Get the path for the current planning blackboard file."""
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        return os.path.join(self.blackboard_dir, f"planning_blackboard_{timestamp}.md")

    def get_editor_blackboard_path(self) -> str:
        """Get the path for the editor blackboard file."""
        return os.path.join(self.blackboard_dir, self.editor_blackboard_file)

    def get_research_blackboard_path(self) -> str:
        """Get the path for the research blackboard file."""
        return os.path.join(self.blackboard_dir, self.research_blackboard_file)

    def read_planning_blackboard(self) -> str:
        """Read the most recent planning blackboard content."""
        # Find all planning blackboard files
        planning_files = []
        if os.path.exists(self.blackboard_dir):
            for file in os.listdir(self.blackboard_dir):
                if file.startswith("planning_blackboard_") and file.endswith(".md"):
                    planning_files.append(file)

        if not planning_files:
            return ""

        # Get the most recent one (lexicographically sorted due to timestamp format)
        most_recent = sorted(planning_files)[-1]
        planning_path = os.path.join(self.blackboard_dir, most_recent)

        try:
            with open(planning_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read planning blackboard {planning_path}: {e}")
            return ""

    def read_editor_blackboard(self) -> str:
        """Read the editor blackboard content."""
        editor_path = self.get_editor_blackboard_path()
        if not os.path.exists(editor_path):
            return ""

        try:
            with open(editor_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read editor blackboard {editor_path}: {e}")
            return ""

    def read_research_blackboard(self) -> str:
        """Read the research blackboard content."""
        research_path = self.get_research_blackboard_path()
        if not os.path.exists(research_path):
            return ""

        try:
            with open(research_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read research blackboard {research_path}: {e}")
            return ""

    def write_planning_blackboard(self, content: str) -> str:
        """Write content to a new planning blackboard file."""
        planning_path = self.get_planning_blackboard_path()

        try:
            with open(planning_path, "w") as f:
                f.write(content)
            print(f"Planning blackboard written to: {planning_path}")
            return planning_path
        except Exception as e:
            print(f"Error writing planning blackboard {planning_path}: {e}")
            raise

    def write_editor_blackboard(self, content: str) -> str:
        """Write content to the editor blackboard file (overwrites existing)."""
        editor_path = self.get_editor_blackboard_path()

        try:
            with open(editor_path, "w") as f:
                f.write(content)
            print(f"Editor blackboard written to: {editor_path}")
            return editor_path
        except Exception as e:
            print(f"Error writing editor blackboard {editor_path}: {e}")
            raise

    def append_editor_blackboard(self, content: str) -> str:
        """Append content to the editor blackboard file."""
        editor_path = self.get_editor_blackboard_path()

        try:
            with open(editor_path, "a") as f:
                f.write(content)
            print(f"Content appended to editor blackboard: {editor_path}")
            return editor_path
        except Exception as e:
            print(f"Error appending to editor blackboard {editor_path}: {e}")
            raise

    def write_research_blackboard(self, content: str) -> str:
        """Write content to the research blackboard file (overwrites existing)."""
        research_path = self.get_research_blackboard_path()

        try:
            with open(research_path, "w") as f:
                f.write(content)
            print(f"Research blackboard written to: {research_path}")
            return research_path
        except Exception as e:
            print(f"Error writing research blackboard {research_path}: {e}")
            raise

    def append_research_blackboard(self, content: str) -> str:
        """Append content to the research blackboard file."""
        research_path = self.get_research_blackboard_path()

        try:
            with open(research_path, "a") as f:
                f.write(content)
            print(f"Content appended to research blackboard: {research_path}")
            return research_path
        except Exception as e:
            print(f"Error appending to research blackboard {research_path}: {e}")
            raise

    def clear_editor_blackboard(self) -> None:
        """Clear the editor blackboard file."""
        editor_path = self.get_editor_blackboard_path()

        if os.path.exists(editor_path):
            try:
                os.remove(editor_path)
                print(f"Editor blackboard cleared: {editor_path}")
            except Exception as e:
                print(f"Error clearing editor blackboard {editor_path}: {e}")
                raise

    def get_all_blackboard_content(self) -> dict:
        """Get all blackboard content as a dictionary."""
        return {
            "planning": self.read_planning_blackboard(),
            "editor": self.read_editor_blackboard(),
            "research": self.read_research_blackboard(),
        }

    def blackboard_exists(self, blackboard_type: str) -> bool:
        """Check if a specific blackboard file exists."""
        if blackboard_type == "editor":
            return os.path.exists(self.get_editor_blackboard_path())
        elif blackboard_type == "research":
            return os.path.exists(self.get_research_blackboard_path())
        elif blackboard_type == "planning":
            # Check if any planning blackboard exists
            if os.path.exists(self.blackboard_dir):
                for file in os.listdir(self.blackboard_dir):
                    if file.startswith("planning_blackboard_") and file.endswith(".md"):
                        return True
            return False
        else:
            raise ValueError(f"Unknown blackboard type: {blackboard_type}")
