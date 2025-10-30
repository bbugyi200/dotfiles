import subprocess
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from shared_utils import log_prompt_and_response


class GeminiCommandWrapper:
    def __init__(self):
        self.decision_counts = None
        self.agent_type = "agent"
        self.iteration = None
        self.workflow_tag = None

    def set_decision_counts(self, decision_counts: dict):
        """Set the decision counts for display after prompts."""
        self.decision_counts = decision_counts

    def set_logging_context(
        self,
        agent_type: str = "agent",
        iteration: Optional[int] = None,
        workflow_tag: Optional[str] = None,
    ):
        """Set the context for logging prompts and responses."""
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag

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
                    "--use_google_internal_system_prompt",
                    "--yolo",
                ],
                input=query,
                capture_output=True,
                text=True,
                check=True,
            )
            response_content = result.stdout.strip()

            # Log the prompt and response to gai.md
            log_prompt_and_response(
                prompt=query,
                response=response_content,
                agent_type=self.agent_type,
                iteration=self.iteration,
                workflow_tag=self.workflow_tag,
            )

            return AIMessage(content=response_content)
        except subprocess.CalledProcessError as e:
            error_content = f"Error running gemini command: {e.stderr}"

            # Log the error too
            log_prompt_and_response(
                prompt=query,
                response=error_content,
                agent_type=f"{self.agent_type}_ERROR",
                iteration=self.iteration,
                workflow_tag=self.workflow_tag,
            )

            return AIMessage(content=error_content)
        except Exception as e:
            error_content = f"Error: {str(e)}"

            # Log the error too
            log_prompt_and_response(
                prompt=query,
                response=error_content,
                agent_type=f"{self.agent_type}_ERROR",
                iteration=self.iteration,
                workflow_tag=self.workflow_tag,
            )

            return AIMessage(content=error_content)
