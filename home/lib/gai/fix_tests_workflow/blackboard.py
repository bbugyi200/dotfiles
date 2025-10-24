import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


class BlackboardManager:
    """Manages blackboard files for the fix-tests workflow."""

    def __init__(self, blackboard_dir: str):
        self.blackboard_dir = blackboard_dir
        self.planning_blackboard_file = "planning_blackboard.md"
        self.editor_blackboard_file = "editor_blackboard.md"
        self.research_blackboard_file = "research_blackboard.md"

        # Ensure blackboard directory exists
        Path(self.blackboard_dir).mkdir(parents=True, exist_ok=True)

    def _get_timestamp(self) -> str:
        """Get current timestamp in YYmmdd_HHMMSS format using NYC Eastern Time."""
        eastern = ZoneInfo("America/New_York")
        return datetime.now(eastern).strftime("%y%m%d_%H%M%S")

    def get_planning_blackboard_path(self) -> str:
        """Get the path for the planning blackboard file."""
        return os.path.join(self.blackboard_dir, self.planning_blackboard_file)

    def get_editor_blackboard_path(self) -> str:
        """Get the path for the editor blackboard file."""
        return os.path.join(self.blackboard_dir, self.editor_blackboard_file)

    def get_research_blackboard_path(self) -> str:
        """Get the path for the research blackboard file."""
        return os.path.join(self.blackboard_dir, self.research_blackboard_file)

    def read_planning_blackboard(self) -> str:
        """Read the planning blackboard content."""
        planning_path = self.get_planning_blackboard_path()
        if not os.path.exists(planning_path):
            return ""

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

    def add_planning_entry(self, user_prompt: str, agent_response: str) -> str:
        """Add a new planning entry with timestamp headers."""
        planning_path = self.get_planning_blackboard_path()
        timestamp = self._get_timestamp()

        # Create entry with proper markdown format
        entry = f"""# {timestamp}

## {timestamp} (User)

{user_prompt}

## {timestamp} (Agent)

{agent_response}

"""

        try:
            # Always append to planning blackboard
            with open(planning_path, "a") as f:
                f.write(entry)
            print(f"Planning entry added to: {planning_path}")
            return planning_path
        except Exception as e:
            print(f"Error writing to planning blackboard {planning_path}: {e}")
            raise

    def add_editor_entry(self, user_prompt: str, agent_response: str) -> str:
        """Add a new editor entry with timestamp headers."""
        editor_path = self.get_editor_blackboard_path()
        timestamp = self._get_timestamp()

        # Create entry with proper markdown format
        entry = f"""# {timestamp}

## {timestamp} (User)

{user_prompt}

## {timestamp} (Agent)

{agent_response}

"""

        try:
            # Always append to editor blackboard
            with open(editor_path, "a") as f:
                f.write(entry)
            print(f"Editor entry added to: {editor_path}")
            return editor_path
        except Exception as e:
            print(f"Error writing to editor blackboard {editor_path}: {e}")
            raise

    def add_research_entry(self, user_prompt: str, agent_response: str) -> str:
        """Add a new research entry with timestamp headers."""
        research_path = self.get_research_blackboard_path()
        timestamp = self._get_timestamp()

        # Create entry with proper markdown format
        entry = f"""# {timestamp}

## {timestamp} (User)

{user_prompt}

## {timestamp} (Agent)

{agent_response}

"""

        try:
            # Always append to research blackboard
            with open(research_path, "a") as f:
                f.write(entry)
            print(f"Research entry added to: {research_path}")
            return research_path
        except Exception as e:
            print(f"Error writing to research blackboard {research_path}: {e}")
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
            return os.path.exists(self.get_planning_blackboard_path())
        else:
            raise ValueError(f"Unknown blackboard type: {blackboard_type}")
