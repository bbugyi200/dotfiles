import os
import re
import subprocess
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from shared_utils import log_prompt_and_response


class GeminiCommandWrapper:
    def __init__(self, use_api: bool = None):
        self.decision_counts = None
        self.agent_type = "agent"
        self.iteration = None
        self.workflow_tag = None
        self.artifacts_dir = None

        # Determine whether to use API mode
        if use_api is None:
            # Check environment variable or default to CLI
            self.use_api = os.getenv("GAI_USE_GEMINI_API", "false").lower() == "true"
        else:
            self.use_api = use_api

        # Initialize API client if needed
        self.api_client = None
        if self.use_api:
            try:
                from gemini_api_client import GeminiAPIClient

                # Get configuration from environment variables
                endpoint = os.getenv(
                    "GAI_GEMINI_ENDPOINT", "http://localhost:8649/predict"
                )
                model = os.getenv("GAI_GEMINI_MODEL", "gemini-for-google-2.5-pro")
                temperature = float(os.getenv("GAI_GEMINI_TEMPERATURE", "0.1"))
                max_decoder_steps = int(
                    os.getenv("GAI_GEMINI_MAX_DECODER_STEPS", "8192")
                )

                self.api_client = GeminiAPIClient(
                    endpoint=endpoint,
                    model=model,
                    temperature=temperature,
                    max_decoder_steps=max_decoder_steps,
                )
                print(f"✅ Using Gemini API mode with endpoint: {endpoint}")
            except ImportError as e:
                print(f"⚠️ Failed to import GeminiAPIClient: {e}")
                print("⚠️ Falling back to CLI mode")
                self.use_api = False
            except Exception as e:
                print(f"⚠️ Failed to initialize Gemini API client: {e}")
                print("⚠️ Falling back to CLI mode")
                self.use_api = False

    def set_decision_counts(self, decision_counts: dict):
        """Set the decision counts for display after prompts."""
        self.decision_counts = decision_counts

    def set_logging_context(
        self,
        agent_type: str = "agent",
        iteration: Optional[int] = None,
        workflow_tag: Optional[str] = None,
        artifacts_dir: Optional[str] = None,
    ):
        """Set the context for logging prompts and responses."""
        self.agent_type = agent_type
        self.iteration = iteration
        self.workflow_tag = workflow_tag
        self.artifacts_dir = artifacts_dir

    def _display_decision_counts(self):
        """Display the planning agent decision counts."""
        if self.decision_counts is not None:
            print("PLANNING AGENT DECISION COUNTS:")
            print(f"- New Editor: {self.decision_counts.get('new_editor', 0)}")
            print(f"- Existing Editor: {self.decision_counts.get('next_editor', 0)}")
            print(f"- Researcher: {self.decision_counts.get('research', 0)}")
            print()

    def _extract_file_paths(self, text: str) -> List[str]:
        """Extract all file paths prefixed with '@' from the text."""
        # Match @filepath patterns, where filepath can contain common path characters
        # Pattern matches: @/path/to/file, @./relative/path, @~/home/path, @filename.ext
        pattern = r"@([^\s\[\](){}|&;<>]+)"
        matches = re.findall(pattern, text)
        return matches

    def _expand_file_contents(self, text: str) -> str:
        """Replace all '@filepath' references with the actual file contents."""
        file_paths = self._extract_file_paths(text)

        if not file_paths:
            return text

        expanded_text = text
        file_contents_sections = []

        for file_path in file_paths:
            try:
                # Expand tilde to home directory if present
                expanded_path = os.path.expanduser(file_path)

                with open(expanded_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                # Create a clearly delimited section for this file
                file_section = f"""
================================================================================
FILE: {file_path}
================================================================================
{file_content}
================================================================================
END OF FILE: {file_path}
================================================================================
"""
                file_contents_sections.append(file_section)

                # Remove the @filepath reference from the original text
                expanded_text = expanded_text.replace(
                    f"@{file_path}", f"[EXPANDED: {file_path}]"
                )

            except FileNotFoundError:
                print(f"⚠️ Warning: File not found: {file_path}")
                expanded_text = expanded_text.replace(
                    f"@{file_path}", f"[FILE NOT FOUND: {file_path}]"
                )
            except Exception as e:
                print(f"⚠️ Warning: Error reading file {file_path}: {e}")
                expanded_text = expanded_text.replace(
                    f"@{file_path}", f"[ERROR READING FILE: {file_path}]"
                )

        # Prepend all file contents to the beginning of the expanded text
        if file_contents_sections:
            file_contents_prefix = "".join(file_contents_sections) + "\n\n"
            expanded_text = file_contents_prefix + expanded_text

        return expanded_text

    def invoke(
        self, messages: List[HumanMessage | AIMessage | SystemMessage]
    ) -> AIMessage:
        # Extract query for CLI mode or use messages directly for API mode
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query and not self.use_api:
            return AIMessage(content="No query found in messages")

        # Pretty print the prompt that will be sent to Gemini
        print("=" * 80)
        if self.use_api:
            print("GEMINI API REQUEST:")
        else:
            print("GEMINI CLI PROMPT:")
        print("=" * 80)
        if self.use_api and len(messages) > 1:
            # Show all messages for API mode
            for msg in messages:
                print(f"{msg.role.upper()}: {msg.content[:200]}...")
        else:
            print(query)
        print("=" * 80)
        print()

        # Display decision counts after the prompt
        self._display_decision_counts()

        try:
            if self.use_api and self.api_client:
                # Use API mode with tool calling - expand file contents in messages before sending
                expanded_messages = []
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        # Expand file contents for human messages
                        expanded_content = self._expand_file_contents(msg.content)
                        expanded_messages.append(HumanMessage(content=expanded_content))
                    else:
                        # Keep other message types unchanged
                        expanded_messages.append(msg)

                # Use tool calling workflow instead of direct API call
                try:
                    from tool_calling_workflow import invoke_with_tools

                    response_content = invoke_with_tools(
                        expanded_messages, tools_available=True, max_iterations=5
                    )
                except ImportError:
                    # Fallback to direct API call if tool calling not available
                    print(
                        "⚠️ Tool calling workflow not available, falling back to direct API call"
                    )
                    response = self.api_client.invoke(expanded_messages)
                    response_content = response.content
            else:
                # Use CLI mode
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
            if self.artifacts_dir:
                if self.use_api:
                    # For API mode, log the expanded content
                    expanded_query = ""
                    for msg in expanded_messages:
                        if isinstance(msg, HumanMessage):
                            expanded_query = msg.content
                            break
                    log_prompt_and_response(
                        prompt=expanded_query
                        or f"API request with {len(expanded_messages)} messages",
                        response=response_content,
                        artifacts_dir=self.artifacts_dir,
                        agent_type=self.agent_type,
                        iteration=self.iteration,
                        workflow_tag=self.workflow_tag,
                    )
                else:
                    # For CLI mode, log the original query
                    log_prompt_and_response(
                        prompt=query,
                        response=response_content,
                        artifacts_dir=self.artifacts_dir,
                        agent_type=self.agent_type,
                        iteration=self.iteration,
                        workflow_tag=self.workflow_tag,
                    )

            return AIMessage(content=response_content)

        except subprocess.CalledProcessError as e:
            error_content = f"Error running gemini command: {e.stderr}"

            # Log the error too
            if self.artifacts_dir:
                log_prompt_and_response(
                    prompt=query,
                    response=error_content,
                    artifacts_dir=self.artifacts_dir,
                    agent_type=f"{self.agent_type}_ERROR",
                    iteration=self.iteration,
                    workflow_tag=self.workflow_tag,
                )

            return AIMessage(content=error_content)
        except Exception as e:
            error_content = f"Error: {str(e)}"

            # Log the error too
            if self.artifacts_dir:
                log_prompt_and_response(
                    prompt=(
                        query
                        if not self.use_api
                        else f"API request with {len(messages)} messages"
                    ),
                    response=error_content,
                    artifacts_dir=self.artifacts_dir,
                    agent_type=f"{self.agent_type}_ERROR",
                    iteration=self.iteration,
                    workflow_tag=self.workflow_tag,
                )

            return AIMessage(content=error_content)
