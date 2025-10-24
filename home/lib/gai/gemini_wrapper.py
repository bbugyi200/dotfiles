import subprocess
from typing import List

from langchain_core.messages import AIMessage, HumanMessage


class GeminiCommandWrapper:
    def __init__(self):
        self.decision_counts = None

    def set_decision_counts(self, decision_counts: dict):
        """Set the decision counts for display after prompts."""
        self.decision_counts = decision_counts

    def _display_decision_counts(self):
        """Display the planning agent decision counts."""
        if self.decision_counts is not None:
            print("PLANNING AGENT DECISION COUNTS:")
            print(f"- New Editor: {self.decision_counts.get('new_editor', 0)}")
            print(f"- Existing Editor: {self.decision_counts.get('next_editor', 0)}")
            print(f"- Researcher: {self.decision_counts.get('research', 0)}")
            print()

    def invoke(self, messages: List[HumanMessage | AIMessage]) -> AIMessage:
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query:
            return AIMessage(content="No query found in messages")

        # Pretty print the prompt that will be sent to Gemini
        print("=" * 80)
        print("GEMINI PROMPT:")
        print("=" * 80)
        print(query)
        print("=" * 80)
        print()

        # Display decision counts after the prompt
        self._display_decision_counts()

        try:
            # Pass query via stdin to avoid "Argument list too long" error
            result = subprocess.run(
                [
                    "/google/bin/releases/gemini-cli/tools/gemini",
                    "--gfg",
                    "--yolo",
                ],
                input=query,
                capture_output=True,
                text=True,
                check=True,
            )
            return AIMessage(content=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            return AIMessage(content=f"Error running gemini command: {e.stderr}")
        except Exception as e:
            return AIMessage(content=f"Error: {str(e)}")
