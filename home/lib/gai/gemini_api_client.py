import json
import urllib.parse
import urllib.request
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class GeminiAPIClient:
    """Direct Gemini API client for GAI workflows."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8649/predict",
        model: str = "gemini-for-google-2.5-pro",
        temperature: float = 0.1,
        max_decoder_steps: int = 8192,
    ):
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_decoder_steps = max_decoder_steps

    def _convert_role(self, role: str) -> str:
        """Convert LangChain role to Gemini API role."""
        if role == "assistant":
            return "MODEL"
        elif role == "user":
            return "USER"
        else:
            return role

    def _form_messages(
        self, messages: List[HumanMessage | AIMessage | SystemMessage]
    ) -> dict:
        """Convert LangChain messages to Gemini API format."""
        contents = []
        system_instruction = None

        for message in messages:
            if isinstance(message, SystemMessage):
                system_instruction = {
                    "parts": [
                        {
                            "text": message.content,
                        }
                    ],
                }
            else:
                # Determine role based on message type
                if isinstance(message, HumanMessage):
                    role = "user"
                elif isinstance(message, AIMessage):
                    role = "assistant"
                else:
                    role = "user"  # Default fallback

                contents.append(
                    {
                        "role": self._convert_role(role),
                        "parts": [
                            {
                                "text": message.content,
                            }
                        ],
                    }
                )

        body = {
            "model": f"models/{self.model}",
            "client_metadata": {
                "feature_name": "gai-workflow",
                "use_type": "CODE_GENERATION",
            },
            "generation_config": {
                "temperature": self.temperature,
                "maxDecoderSteps": self.max_decoder_steps,
            },
            "contents": contents,
        }

        if system_instruction:
            body["system_instruction"] = system_instruction

        return body

    def _make_request(self, body: dict) -> dict:
        """Make HTTP request to Gemini API."""
        headers = {
            "Content-Type": "application/json",
        }

        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            self.endpoint, data=data, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")
                return json.loads(response_data)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            raise Exception(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"URL Error: {e.reason}")

    def _extract_content(self, response: dict) -> str:
        """Extract content from Gemini API response."""
        content = ""

        # Handle Gemini API response format
        if response.get("candidates") and response["candidates"]:
            candidate = response["candidates"][0]
            if candidate.get("finish_reason") == "RECITATION":
                content = "Gemini API response was blocked for violating policy."
            elif (
                candidate.get("content")
                and candidate["content"].get("parts")
                and candidate["content"]["parts"]
            ):
                content = candidate["content"]["parts"][0].get("text", "")

        # Handle legacy response format (from your CodeCompanion implementation)
        elif response.get("outputs") and response["outputs"]:
            if response.get("output_blocked"):
                content = "Gemini API response was blocked for violating policy."
            else:
                for output_item in response["outputs"]:
                    if output_item.get("content"):
                        content += output_item["content"]

        # Handle old array response format
        elif isinstance(response, list) and response:
            for output_item in response:
                if output_item.get("content"):
                    content += output_item["content"]

        return content

    def invoke(
        self, messages: List[HumanMessage | AIMessage | SystemMessage]
    ) -> AIMessage:
        """Send messages to Gemini API and return response."""
        try:
            # Convert messages to API format
            body = self._form_messages(messages)

            # Make API request
            response = self._make_request(body)

            # Extract content from response
            content = self._extract_content(response)

            if not content:
                content = "No content received from Gemini API"

            return AIMessage(content=content)

        except Exception as e:
            error_content = f"Error calling Gemini API: {str(e)}"
            return AIMessage(content=error_content)
