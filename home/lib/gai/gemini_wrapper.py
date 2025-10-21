import subprocess
from typing import List

from langchain_core.messages import AIMessage, HumanMessage


class GeminiCommandWrapper:
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
