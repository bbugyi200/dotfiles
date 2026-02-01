"""Agent prompt panel widget for the ace TUI."""

from pathlib import Path

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
from textual.widgets import Static

from ..models.agent import Agent, AgentType


class AgentPromptPanel(Static):
    """Top panel showing agent details and the input prompt."""

    def update_display(self, agent: Agent) -> None:
        """Update with agent information and prompt.

        Args:
            agent: The Agent to display.
        """
        # Check if this is a workflow agent - display workflow-specific info
        if agent.agent_type == AgentType.WORKFLOW:
            self._update_workflow_display(agent)
            return

        header_text = Text()

        # Header - AGENT DETAILS
        header_text.append("AGENT DETAILS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # ChangeSpec name
        header_text.append("ChangeSpec: ", style="bold #87D7FF")
        header_text.append(f"{agent.cl_name}", style="#00D7AF")
        if agent.cl_num:
            cl_id = agent.cl_num.removeprefix("http://cl/")
            header_text.append(" (")
            header_text.append(f"http://cl/{cl_id}", style="bold underline #569CD6")
            header_text.append(")")
        header_text.append("\n")

        # Workspace (if available)
        if agent.workspace_num is not None:
            header_text.append("Workspace: ", style="bold #87D7FF")
            header_text.append(f"#{agent.workspace_num}\n", style="#5FD7FF")

        # Workflow (if available)
        if agent.workflow:
            header_text.append("Workflow: ", style="bold #87D7FF")
            header_text.append(f"{agent.workflow}\n")

        # PID (if available)
        if agent.pid:
            header_text.append("PID: ", style="bold #87D7FF")
            header_text.append(f"{agent.pid}\n", style="#FF87D7 bold")

        # New CL Name (for NEW CL agents)
        if agent.new_cl_name:
            header_text.append("New CL Name: ", style="bold #87D7FF")
            header_text.append(f"{agent.new_cl_name}", style="#00D7AF bold")
            if agent.new_cl_url:
                cl_id = agent.new_cl_url.removeprefix("http://cl/")
                header_text.append(" (")
                header_text.append(f"http://cl/{cl_id}", style="bold underline #569CD6")
                header_text.append(")")
            header_text.append("\n")

        # Proposal ID (for NEW PROPOSAL agents)
        if agent.proposal_id:
            header_text.append("New Proposal ID: ", style="bold #87D7FF")
            header_text.append(f"{agent.proposal_id}\n", style="#AF87D7 bold")

        # BUG field (if available)
        if agent.bug:
            header_text.append("BUG: ", style="bold #87D7FF")
            header_text.append(f"{agent.bug}\n", style="bold underline #569CD6")

        # Timestamp (when agent started)
        header_text.append("Timestamp: ", style="bold #87D7FF")
        header_text.append(f"{agent.start_time_display}\n", style="#D7D7FF")

        # Separator
        header_text.append("\n")
        header_text.append("─" * 50 + "\n", style="dim")
        header_text.append("\n")

        # AGENT PROMPT section
        header_text.append("AGENT PROMPT\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # Get and display prompt content
        prompt_content = self._get_prompt_content(agent)
        if prompt_content:
            # Render markdown with syntax highlighting
            prompt_syntax = Syntax(
                prompt_content,
                "markdown",
                theme="monokai",
                word_wrap=True,
            )

            # For completed agents, also show the response
            if agent.status in ("NO CHANGES", "NEW CL", "NEW PROPOSAL"):
                reply_header = Text()
                reply_header.append("\n")
                reply_header.append("─" * 50 + "\n", style="dim")
                reply_header.append("\n")
                reply_header.append("AGENT CHAT\n", style="bold #D7AF5F underline")
                reply_header.append("\n")

                response_content = agent.get_response_content()
                if response_content:
                    response_syntax = Syntax(
                        response_content,
                        "markdown",
                        theme="monokai",
                        word_wrap=True,
                    )
                    self.update(
                        Group(header_text, prompt_syntax, reply_header, response_syntax)
                    )
                else:
                    reply_header.append("No response file found.\n", style="dim italic")
                    self.update(Group(header_text, prompt_syntax, reply_header))
            else:
                self.update(Group(header_text, prompt_syntax))
        else:
            header_text.append("No prompt file found.\n", style="dim italic")
            self.update(header_text)

    def _get_prompt_content(self, agent: Agent) -> str | None:
        """Get the prompt content for the agent.

        Args:
            agent: The agent to get prompt for.

        Returns:
            Prompt content, or None if not found.
        """
        artifacts_dir = agent.get_artifacts_dir()
        if artifacts_dir is None:
            return None

        artifacts_path = Path(artifacts_dir)

        # Look for any *_prompt.md file
        prompt_files = list(artifacts_path.glob("*_prompt.md"))

        if not prompt_files:
            return None

        # Sort by modification time to get the most recent
        prompt_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        try:
            with open(prompt_files[0], encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def _update_workflow_display(self, agent: Agent) -> None:
        """Update display for a workflow agent.

        Args:
            agent: The workflow agent to display.
        """
        header_text = Text()

        # Header - WORKFLOW DETAILS
        header_text.append("WORKFLOW DETAILS\n", style="bold #D7AF5F underline")
        header_text.append("\n")

        # Workflow name (stored in workflow field)
        header_text.append("Workflow: ", style="bold #87D7FF")
        header_text.append(f"{agent.workflow or 'unknown'}\n", style="#AF87D7 bold")

        # ChangeSpec name
        header_text.append("ChangeSpec: ", style="bold #87D7FF")
        header_text.append(f"{agent.cl_name}\n", style="#00D7AF")

        # Status
        header_text.append("Status: ", style="bold #87D7FF")
        status_style = {
            "RUNNING": "#87D7FF",
            "WAITING INPUT": "#FFAF5F",
            "COMPLETED": "#5FD75F",
            "FAILED": "#FF5F5F",
        }.get(agent.status, "#D7D7FF")
        header_text.append(f"{agent.status}\n", style=status_style)

        # Timestamp
        header_text.append("Timestamp: ", style="bold #87D7FF")
        header_text.append(f"{agent.start_time_display}\n", style="#D7D7FF")

        # Note about workflow step progress
        header_text.append("\n")
        header_text.append("─" * 50 + "\n", style="dim")
        header_text.append("\n")
        header_text.append("WORKFLOW STEPS\n", style="bold #D7AF5F underline")
        header_text.append("\n")
        header_text.append(
            "Step details are available in workflow_state.json\n", style="dim italic"
        )

        self.update(header_text)

    def show_empty(self) -> None:
        """Show empty state."""
        text = Text("No agent selected", style="dim italic")
        self.update(text)
