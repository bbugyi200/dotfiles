from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
import os

# Set up Gemini model
model = ChatGoogleGenerativeAI(
    model="gemini-for-google-2.5-pro", google_api_key=os.environ["GEMINI_API_KEY"]
)


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
    # Example 1: Simple conversation
    response = app.invoke(
        {"messages": [HumanMessage(content="What's the weather like in New York?")]}
    )
    print("Response:", response["messages"][-1].content)

    # Example 2: Math calculation
    response = app.invoke({"messages": [HumanMessage(content="Calculate 15 * 8 + 32")]})
    print("Response:", response["messages"][-1].content)

    # Example 3: Multi-step conversation
    config = {"configurable": {"thread_id": "conversation-1"}}

    # Add checkpointer for conversation memory (optional)
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    app_with_memory = workflow.compile(checkpointer=checkpointer)

    # First message
    response = app_with_memory.invoke(
        {"messages": [HumanMessage(content="What's the weather in London?")]}, config
    )

    # Follow-up message (remembers context)
    response = app_with_memory.invoke(
        {"messages": [HumanMessage(content="And what about Tokyo?")]}, config
    )

    print("Final response:", response["messages"][-1].content)
