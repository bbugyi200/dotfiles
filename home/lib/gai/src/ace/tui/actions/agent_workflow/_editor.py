"""Editor integration for agent workflow (external editor, workflow YAML)."""

from __future__ import annotations

import os


class EditorMixin:
    """Mixin providing editor integration for agent prompts and workflows."""

    def _open_editor_for_agent_prompt(self, initial_content: str = "") -> str | None:
        """Suspend TUI and open editor for prompt input.

        Args:
            initial_content: Initial text to populate the editor with.

        Returns:
            The prompt content, or None if empty/cancelled.
        """
        import subprocess
        import tempfile

        def run_editor() -> str | None:
            fd, temp_path = tempfile.mkstemp(suffix=".md", prefix="gai_ace_prompt_")
            # Write initial content if provided
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(initial_content)

            editor = os.environ.get("EDITOR", "nvim")

            result = subprocess.run([editor, temp_path], check=False)
            if result.returncode != 0:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                return None

            try:
                with open(temp_path, encoding="utf-8") as f:
                    content = f.read().strip()
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            return content if content else None

        with self.suspend():  # type: ignore[attr-defined]
            return run_editor()

    def _open_workflow_yaml_editor(self) -> tuple[str, str] | None:
        """Suspend TUI and open editor for ad-hoc workflow YAML.

        Creates a YAML template, opens it in the user's editor, then saves the
        result to ~/.xprompts/ for execution.

        Returns:
            A (workflow_name, file_path) tuple, or None if cancelled/invalid.
        """
        import subprocess
        import tempfile

        import yaml  # type: ignore[import-untyped]
        from gai_utils import generate_timestamp

        timestamp = generate_timestamp()
        default_name = f"adhoc_{timestamp}"
        template = (
            "# yaml-language-server: $schema="
            + os.path.expanduser("~/lib/gai/xprompts/workflow.schema.json")
            + "\n"
            "\n"
            "steps:\n"
            "  - name: main\n"
            "    prompt: |\n"
            "      <your prompt here>\n"
        )

        def run_editor() -> tuple[str, str] | None:
            fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix="gai_ace_workflow_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(template)

            editor = os.environ.get("EDITOR", "nvim")
            result = subprocess.run([editor, temp_path], check=False)
            if result.returncode != 0:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                return None

            try:
                with open(temp_path, encoding="utf-8") as f:
                    content = f.read()
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            stripped = content.strip()
            if not stripped:
                return None

            # Parse YAML to extract workflow name
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                return None

            if not isinstance(data, dict):
                return None

            workflow_name = default_name

            # Save to ~/.xprompts/
            xprompts_dir = os.path.expanduser("~/.xprompts")
            os.makedirs(xprompts_dir, exist_ok=True)

            dest_path = os.path.join(xprompts_dir, f"{workflow_name}.yml")
            if os.path.exists(dest_path):
                # Append timestamp to avoid collision
                dest_path = os.path.join(
                    xprompts_dir, f"{workflow_name}_{timestamp}.yml"
                )

            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)

            return (workflow_name, dest_path)

        with self.suspend():  # type: ignore[attr-defined]
            return run_editor()
