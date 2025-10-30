"""
LangGraph workflow for tool-calling with Gemini API.
"""

import json
import re
from typing import List, Dict, Any, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from api_tools import AVAILABLE_TOOLS, get_tools_by_name
from gemini_api_client import GeminiAPIClient


class ToolCallingState(TypedDict):
    messages: List[HumanMessage | AIMessage | SystemMessage]
    tools_available: bool
    max_iterations: int
    current_iteration: int
    final_response: str
    errors: List[str]


def create_tool_prompt() -> str:
    """Create a prompt section describing available tools."""
    tool_descriptions = []

    for tool in AVAILABLE_TOOLS:
        # Get tool schema/description
        tool_name = tool.name
        tool_description = tool.description or "No description available"

        # Extract parameter info from the tool's args_schema if available
        params_info = ""
        if hasattr(tool, "args_schema") and tool.args_schema:
            try:
                schema = tool.args_schema.schema()
                properties = schema.get("properties", {})
                required = schema.get("required", [])

                param_list = []
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    required_marker = (
                        " (required)" if param_name in required else " (optional)"
                    )
                    param_list.append(
                        f"  - {param_name} ({param_type}){required_marker}: {param_desc}"
                    )

                if param_list:
                    params_info = "\n" + "\n".join(param_list)
            except Exception:
                params_info = ""

        tool_descriptions.append(
            f"""**{tool_name}**
{tool_description}{params_info}"""
        )

    tools_section = (
        """

# AVAILABLE TOOLS

You have access to the following tools for file operations and shell commands:

"""
        + "\n\n".join(tool_descriptions)
        + """

# TOOL USAGE

To use a tool, format your request as follows:

```tool_call
tool_name: <tool_name>
<parameter_name>: <parameter_value>
<parameter_name>: <parameter_value>
```

Examples:

```tool_call
tool_name: write_file
file_path: /path/to/file.txt
content: Hello, world!
```

```tool_call
tool_name: run_shell_command
command: ls -la
working_directory: /some/directory
```

You can make multiple tool calls in your response. After making tool calls, I will execute them and provide you with the results, then you can continue your work or make additional tool calls as needed.

IMPORTANT: Only use tools when necessary to complete your task. Always explain what you're doing and why you're using each tool.
"""
    )

    return tools_section


def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Extract tool calls from the response text."""
    tool_calls = []

    # Pattern to match tool_call blocks
    pattern = r"```tool_call\s*\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)

    for match in matches:
        lines = match.strip().split("\n")
        tool_call = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                tool_call[key.strip()] = value.strip()

        if "tool_name" in tool_call:
            tool_calls.append(tool_call)

    return tool_calls


def execute_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute the extracted tool calls and return results."""
    tools_by_name = get_tools_by_name()
    results = []

    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        if not tool_name:
            results.append(
                {
                    "tool_name": "unknown",
                    "error": "No tool_name specified",
                    "input": tool_call,
                }
            )
            continue

        if tool_name not in tools_by_name:
            results.append(
                {
                    "tool_name": tool_name,
                    "error": f"Unknown tool: {tool_name}",
                    "input": tool_call,
                }
            )
            continue

        tool = tools_by_name[tool_name]

        # Prepare arguments for the tool
        tool_args = {k: v for k, v in tool_call.items() if k != "tool_name"}

        try:
            # Execute the tool
            result = tool.invoke(tool_args)
            results.append(
                {"tool_name": tool_name, "result": result, "input": tool_call}
            )
        except Exception as e:
            results.append(
                {"tool_name": tool_name, "error": str(e), "input": tool_call}
            )

    return results


def format_tool_results(results: List[Dict[str, Any]]) -> str:
    """Format tool execution results for the model."""
    if not results:
        return ""

    formatted = "\n# TOOL EXECUTION RESULTS\n\n"

    for i, result in enumerate(results, 1):
        tool_name = result.get("tool_name", "unknown")
        formatted += f"## Tool Call {i}: {tool_name}\n\n"

        # Show the input
        formatted += (
            f"**Input:**\n```\n{json.dumps(result.get('input', {}), indent=2)}\n```\n\n"
        )

        # Show the result or error
        if "error" in result:
            formatted += f"**Error:** {result['error']}\n\n"
        else:
            formatted += (
                f"**Result:**\n```\n{result.get('result', 'No result')}\n```\n\n"
            )

        formatted += "---\n\n"

    return formatted


def initialize_tool_calling(state: ToolCallingState) -> ToolCallingState:
    """Initialize the tool calling workflow."""
    # Add tool descriptions to the first human message
    if state["messages"] and isinstance(state["messages"][-1], HumanMessage):
        # Get the original message content
        original_content = state["messages"][-1].content

        # Add tools section if tools are available
        if state["tools_available"]:
            enhanced_content = original_content + create_tool_prompt()

            # Replace the last message with enhanced version
            enhanced_messages = state["messages"][:-1] + [
                HumanMessage(content=enhanced_content)
            ]
        else:
            enhanced_messages = state["messages"]
    else:
        enhanced_messages = state["messages"]

    return {
        **state,
        "messages": enhanced_messages,
        "current_iteration": 0,
        "final_response": "",
        "errors": [],
    }


def call_gemini_api(state: ToolCallingState) -> ToolCallingState:
    """Call the Gemini API with the current messages."""
    client = GeminiAPIClient()

    try:
        response = client.invoke(state["messages"])

        # Add the response to messages
        updated_messages = state["messages"] + [response]

        return {
            **state,
            "messages": updated_messages,
            "current_iteration": state["current_iteration"] + 1,
        }

    except Exception as e:
        error_msg = f"Error calling Gemini API: {str(e)}"
        return {
            **state,
            "errors": state["errors"] + [error_msg],
            "final_response": error_msg,
        }


def process_response(state: ToolCallingState) -> ToolCallingState:
    """Process the API response for tool calls."""
    if not state["messages"]:
        return state

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return state

    response_content = last_message.content

    # Check if tools are available and extract tool calls
    if state["tools_available"]:
        tool_calls = extract_tool_calls(response_content)

        if tool_calls:
            # Execute the tool calls
            results = execute_tool_calls(tool_calls)

            # Format results for the model
            results_text = format_tool_results(results)

            # Add results as a new human message
            updated_messages = state["messages"] + [
                HumanMessage(
                    content=results_text
                    + "\nPlease continue based on these tool results."
                )
            ]

            return {**state, "messages": updated_messages}

    # No tool calls found, this is the final response
    return {**state, "final_response": response_content}


def should_continue(state: ToolCallingState) -> str:
    """Determine if we should continue the tool calling loop."""
    # Check if we have a final response
    if state["final_response"]:
        return "end"

    # Check if we've hit max iterations
    if state["current_iteration"] >= state["max_iterations"]:
        return "end"

    # Check if we have errors
    if state["errors"]:
        return "end"

    # Continue if we don't have a final response yet
    return "continue"


def finalize_response(state: ToolCallingState) -> ToolCallingState:
    """Finalize the response."""
    if not state["final_response"] and state["messages"]:
        # Use the last AI message as final response
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage):
            return {**state, "final_response": last_message.content}

    return state


def create_tool_calling_workflow():
    """Create the LangGraph workflow for tool calling."""
    workflow = StateGraph(ToolCallingState)

    # Add nodes
    workflow.add_node("initialize", initialize_tool_calling)
    workflow.add_node("call_api", call_gemini_api)
    workflow.add_node("process_response", process_response)
    workflow.add_node("finalize", finalize_response)

    # Add edges
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "call_api")
    workflow.add_edge("call_api", "process_response")

    # Conditional edge for continuing or ending
    workflow.add_conditional_edges(
        "process_response", should_continue, {"continue": "call_api", "end": "finalize"}
    )

    workflow.add_edge("finalize", END)

    return workflow.compile()


def invoke_with_tools(
    messages: List[HumanMessage | AIMessage | SystemMessage],
    tools_available: bool = True,
    max_iterations: int = 5,
) -> str:
    """
    Invoke the Gemini API with tool calling support.

    Args:
        messages: List of messages to send
        tools_available: Whether to enable tools
        max_iterations: Maximum number of API calls

    Returns:
        Final response string
    """
    workflow = create_tool_calling_workflow()

    initial_state: ToolCallingState = {
        "messages": messages,
        "tools_available": tools_available,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "final_response": "",
        "errors": [],
    }

    try:
        final_state = workflow.invoke(initial_state)
        return final_state.get("final_response", "No response generated")
    except Exception as e:
        return f"Error in tool calling workflow: {str(e)}"
