import subprocess

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import START, MessagesState, StateGraph


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


# Define the agent function
def call_model(state: MessagesState):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


# Create the graph
workflow = StateGraph(MessagesState)

# Add nodes
workflow.add_node("agent", call_model)

# Add edges
workflow.add_edge(START, "agent")

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
        print("Please provide a query as a command line argument.")
        sys.exit(1)
