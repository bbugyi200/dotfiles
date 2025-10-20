import json
import subprocess

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


class GeminiCommandWrapper:
    def invoke(self, messages):
        # Extract the last human message as the query
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query:
            return AIMessage(content="No query found in messages")

        try:
            # Run the gemini command
            result = subprocess.run(
                ["/google/bin/releases/gemini-cli/tools/gemini", "--gfg", "-y", query],
                capture_output=True,
                text=True,
                check=True,
            )
            return AIMessage(content=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            return AIMessage(content=f"Error running gemini command: {e.stderr}")
        except Exception as e:
            return AIMessage(content=f"Error: {str(e)}")

    def bind_tools(self, tools):
        # For simplicity, return self since we're not using tools with command wrapper
        return self


# Set up Gemini model wrapper
model = GeminiCommandWrapper()


# Define a simple tool
@tool
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    # Mock weather data - in reality, you'd call a weather API
    weather_data = {
        "New York": "Sunny, 72°F",
        "London": "Cloudy, 15°C",
        "Tokyo": "Rainy, 20°C",
    }
    return weather_data.get(location, f"Weather data not available for {location}")


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        result = eval(expression)  # Note: In production, use a safer evaluation method
        return f"The result is: {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"


# Bind tools to the model
tools = [get_weather, calculate]
model_with_tools = model.bind_tools(tools)


# Define the agent function
def call_model(state: MessagesState):
    messages = state["messages"]
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


# Create the graph
workflow = StateGraph(MessagesState)

# Add nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

# Add edges
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    tools_condition,  # This checks if the model wants to call tools
)
workflow.add_edge("tools", "agent")

# Compile the graph
app = workflow.compile()

# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Use command line argument as query
        query = " ".join(sys.argv[1:])
        response = app.invoke({"messages": [HumanMessage(content=query)]})
        print(response["messages"][-1].content)
    else:
        # Example 1: Simple conversation
        response = app.invoke(
            {"messages": [HumanMessage(content="What's the weather like in New York?")]}
        )
        print("Response:", response["messages"][-1].content)

        # Example 2: Math calculation
        response = app.invoke(
            {"messages": [HumanMessage(content="Calculate 15 * 8 + 32")]}
        )
        print("Response:", response["messages"][-1].content)
