import os
import subprocess
from typing import List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from workflow_base import BaseWorkflow


class YAQsState(TypedDict):
    artifacts_dir: str
    yaqs_question: str
    question_saved: bool
    failure_reason: Optional[str]
    messages: List[HumanMessage | AIMessage]


class GeminiCommandWrapper:
    def invoke(self, messages):
        query = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                break

        if not query:
            return AIMessage(content="No query found in messages")

        try:
            result = subprocess.run(
                [
                    "/google/bin/releases/gemini-cli/tools/gemini",
                    "--gfg",
                    "--yolo",
                    query,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return AIMessage(content=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            return AIMessage(content=f"Error running gemini command: {e.stderr}")
        except Exception as e:
            return AIMessage(content=f"Error: {str(e)}")


def run_shell_command(
    cmd: str, capture_output: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
    )


def read_artifact_file(file_path: str) -> str:
    """Read the contents of an artifact file."""
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"


def extract_test_command_from_artifacts(artifacts_dir: str) -> str:
    """Extract the test command from agent response artifacts."""
    # Look for the test command in agent response files
    try:
        for file in os.listdir(artifacts_dir):
            if file.startswith("agent_") and file.endswith("_response.txt"):
                artifact_path = os.path.join(artifacts_dir, file)
                content = read_artifact_file(artifact_path)
                # Look for test command pattern in the response
                lines = content.split("\n")
                for line in lines:
                    if "Test command:" in line:
                        return line.split("Test command:", 1)[1].strip()
    except Exception:
        pass

    # Fallback: try to find it in other artifacts
    try:
        # Check if there's a summary file or other artifacts that might contain it
        for filename in ["test_output.txt", "cl_description.txt"]:
            artifact_path = os.path.join(artifacts_dir, filename)
            if os.path.exists(artifact_path):
                content = read_artifact_file(artifact_path)
                if content.strip().startswith("#"):
                    # First line might be the test command
                    first_line = content.split("\n")[0]
                    if first_line.startswith("# "):
                        return first_line[2:].strip()
    except Exception:
        pass

    return "Unknown test command"


def collect_artifacts_summary(artifacts_dir: str) -> str:
    """Collect and summarize all artifacts from the failed fix-test workflow."""
    artifacts_summary = ""

    # Key artifacts to include in the summary
    key_artifacts = ["test_output.txt", "cl_description.txt", "current_diff.txt"]

    # Add initial artifacts
    for artifact_name in key_artifacts:
        artifact_path = os.path.join(artifacts_dir, artifact_name)
        if os.path.exists(artifact_path):
            content = read_artifact_file(artifact_path)
            artifacts_summary += f"\n=== {artifact_name} ===\n{content}\n"

    # Add research artifacts if they exist
    research_artifacts = ["research_summary.md", "research_resources.txt"]
    for research_artifact in research_artifacts:
        artifact_path = os.path.join(artifacts_dir, research_artifact)
        if os.path.exists(artifact_path):
            content = read_artifact_file(artifact_path)
            artifacts_summary += f"\n=== {research_artifact} ===\n{content}\n"

    # Add agent artifacts (responses and changes)
    agent_files = []
    try:
        for file in os.listdir(artifacts_dir):
            if file.startswith("agent_") and (
                file.endswith("_response.txt")
                or file.endswith("_changes.diff")
                or file.endswith("_test_failure.txt")
            ):
                agent_files.append(file)

        # Sort agent files to maintain order
        agent_files.sort()

        for agent_file in agent_files:
            artifact_path = os.path.join(artifacts_dir, agent_file)
            content = read_artifact_file(artifact_path)
            artifacts_summary += f"\n=== {agent_file} ===\n{content}\n"

    except Exception as e:
        artifacts_summary += f"\nError collecting agent artifacts: {str(e)}\n"

    return artifacts_summary


def build_yaqs_prompt(state: YAQsState) -> str:
    """Build the prompt for generating a YAQs question."""

    # Extract test command from artifacts
    test_command = extract_test_command_from_artifacts(state["artifacts_dir"])

    # Collect all artifacts
    artifacts_summary = collect_artifacts_summary(state["artifacts_dir"])

    prompt = f"""You are a technical expert helping to create a comprehensive YAQs (internal StackOverflow) question about a test failure that couldn't be automatically fixed.

CONTEXT:
- Test command: {test_command}
- A fix-test workflow attempted to automatically fix this test but failed after 10 AI agent attempts
- After the 5th failure, a research workflow was run to discover additional insights and resources
- All artifacts from the failed workflow are provided below, including research findings

YOUR TASK:
Create a well-structured YAQs question that includes:
1. A clear, descriptive title
2. A comprehensive problem description that includes:
   - What the test failure is
   - What was attempted to fix it (summarize the AI agents' approaches)
   - What research was conducted and what insights were discovered
   - Current state/symptoms
3. Relevant code snippets and error messages
4. What has been tried and didn't work
5. Suspected root causes or areas to investigate (including from research findings)
6. Specific questions asking for help

ARTIFACTS FROM FAILED FIX ATTEMPT:
{artifacts_summary}

FORMAT YOUR RESPONSE AS A COMPLETE YAQS QUESTION:
Please structure your response as a ready-to-post YAQs question with proper formatting, including:
- Title (use ## for the title)
- Problem description 
- Code blocks (use ``` for code)
- Clear sections for what was tried
- A section highlighting research findings and insights
- Specific questions at the end

Focus on being helpful to other developers who might encounter similar issues.
"""

    return prompt


def generate_yaqs_question(state: YAQsState) -> YAQsState:
    """Generate a YAQs question based on the failed fix-test artifacts."""
    print("Generating YAQs question from failed fix-test artifacts...")

    # Build prompt for Gemini
    prompt = build_yaqs_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("YAQs question generated")

    return {
        **state,
        "yaqs_question": response.content,
        "messages": messages + [response],
    }


def save_yaqs_question(state: YAQsState) -> YAQsState:
    """Save the generated YAQs question to a file."""
    print("Saving YAQs question...")

    # Save to artifacts directory
    yaqs_file_path = os.path.join(state["artifacts_dir"], "yaqs_question.md")

    try:
        with open(yaqs_file_path, "w") as f:
            f.write(state["yaqs_question"])

        print(f"YAQs question saved to: {yaqs_file_path}")

        # Also print the question for immediate viewing
        print("\n" + "=" * 80)
        print("GENERATED YAQS QUESTION:")
        print("=" * 80)
        print(state["yaqs_question"])
        print("=" * 80 + "\n")

        return {**state, "question_saved": True}

    except Exception as e:
        print(f"Error saving YAQs question: {e}")
        return {**state, "question_saved": False, "failure_reason": str(e)}


def handle_yaqs_success(state: YAQsState) -> YAQsState:
    """Handle successful YAQs question generation."""
    print(
        f"""
📝 YAQs question generated successfully!

Question saved in: {state['artifacts_dir']}/yaqs_question.md

You can now copy this question to YAQs to get help from the community.
"""
    )

    # Run bam command to signal completion
    try:
        run_shell_command('bam 3 0.1 "YAQs Question Generated!"', capture_output=False)
    except Exception as e:
        print(f"Warning: Failed to run bam command: {e}")

    return state


def handle_yaqs_failure(state: YAQsState) -> YAQsState:
    """Handle YAQs question generation failure."""
    print(
        f"""
❌ Failed to generate YAQs question.

Error: {state.get('failure_reason', 'Unknown error')}
Artifacts directory: {state['artifacts_dir']}
"""
    )

    return state


class FailedTestSummaryWorkflow(BaseWorkflow):
    """A workflow for generating YAQs questions from failed fix-test attempts."""

    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = artifacts_dir

    @property
    def name(self) -> str:
        return "failed-test-summary"

    @property
    def description(self) -> str:
        return "Generate YAQs questions from failed fix-test workflows"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(YAQsState)

        # Add nodes
        workflow.add_node("generate_question", generate_yaqs_question)
        workflow.add_node("save_question", save_yaqs_question)
        workflow.add_node("success", handle_yaqs_success)
        workflow.add_node("failure", handle_yaqs_failure)

        # Add edges
        workflow.add_edge(START, "generate_question")
        workflow.add_edge("generate_question", "save_question")

        # Add conditional edge based on save success
        workflow.add_conditional_edges(
            "save_question",
            lambda state: "success" if state["question_saved"] else "failure",
            {"success": "success", "failure": "failure"},
        )

        workflow.add_edge("success", END)
        workflow.add_edge("failure", END)

        return workflow.compile()

    def run(self) -> bool:
        """Run the workflow and return True if successful, False otherwise."""
        if not os.path.exists(self.artifacts_dir):
            print(f"Error: Artifacts directory '{self.artifacts_dir}' does not exist")
            return False

        # Create and run the workflow
        app = self.create_workflow()

        initial_state: YAQsState = {
            "artifacts_dir": self.artifacts_dir,
            "yaqs_question": "",
            "question_saved": False,
            "failure_reason": None,
            "messages": [],
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["question_saved"]
        except Exception as e:
            print(f"Error running YAQs workflow: {e}")
            return False
