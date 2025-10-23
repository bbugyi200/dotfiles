import os
from typing import List, Optional, TypedDict

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from shared_utils import collect_all_artifacts, extract_test_command_from_artifacts
from workflow_base import BaseWorkflow


class ResearchState(TypedDict):
    artifacts_dir: str
    research_summary: str
    research_resources: List[str]
    research_saved: bool
    failure_reason: Optional[str]
    messages: List[HumanMessage | AIMessage]
    current_cycle_artifacts: List[str]
    previous_research_cycles: List[List[str]]
    cycle_number: int
    agent_cycles: Optional[List[int]]
    current_cycle: Optional[int]


def collect_artifacts_summary(
    artifacts_dir: str,
    current_cycle_artifacts: List[str] = None,
    previous_research_cycles: List[List[str]] = None,
) -> str:
    """Collect and summarize ALL artifacts from the failed fix-test workflow."""
    # Use the comprehensive artifact collection function
    return collect_all_artifacts(artifacts_dir, exclude_full_outputs=True)


def build_research_prompt(state: ResearchState) -> str:
    """Build the prompt for conducting research on the test failure."""

    # Extract test command from artifacts
    test_command = extract_test_command_from_artifacts(state["artifacts_dir"])

    # Calculate number of agents that have failed so far
    agent_cycles = state.get("agent_cycles", [])
    current_cycle = state.get("current_cycle", 0)

    if agent_cycles and current_cycle is not None:
        # Calculate agents that have failed in completed cycles
        # current_cycle represents the cycle that just completed, so we include it
        agents_failed = sum(agent_cycles[: current_cycle + 1])
        remaining_agents = sum(agent_cycles[current_cycle + 1 :])
        total_agents = sum(agent_cycles)

        agents_desc = f"{agents_failed} attempts by AI agents"
        remaining_desc = f"agents {agents_failed + 1}-{total_agents}"
    else:
        # Fallback to generic description
        agents_desc = "multiple attempts by AI agents"
        remaining_desc = "the remaining agents"

    # Collect artifacts using filtering
    artifacts_summary = collect_artifacts_summary(
        state["artifacts_dir"],
        state.get("current_cycle_artifacts", []),
        state.get("previous_research_cycles", []),
    )

    prompt = f"""You are a senior technical researcher tasked with conducting deep research to help fix a persistent test failure. After {agents_desc} to fix this test, it's clear that additional research and resources are needed.

CONTEXT:
- Test command: {test_command}
- {agents_failed if agent_cycles else "Multiple"} AI agents have already attempted to fix this test and failed
- You need to uncover new information, resources, and insights that weren't apparent in the initial attempts

YOUR RESEARCH MISSION:
Use ALL available tools and resources at your disposal to discover:

1. **Code Search & Analysis:**
   - Search the codebase for similar test patterns, related functionality
   - Find examples of how similar issues were resolved in the past
   - Look for recent changes that might have introduced this issue
   - Identify related components, dependencies, or modules

2. **Documentation & Resources:**
   - Search for relevant documentation, design docs, or technical specifications
   - Look for internal wikis, troubleshooting guides, or known issues
   - Find relevant code reviews, bug reports, or discussions

3. **Historical Analysis:**
   - Search for similar test failures in the past
   - Look for patterns in when this test or similar tests have failed
   - Check for recent changes in related areas

4. **External Research:**
   - Search for relevant Stack Overflow posts, GitHub issues, or technical articles
   - Look for known issues with libraries or frameworks being used
   - Find best practices or common solutions for this type of problem

AVAILABLE ARTIFACTS FROM FAILED ATTEMPTS:
{artifacts_summary}

INSTRUCTIONS:
1. Conduct thorough research using all available search tools (code search, CL search, Moma search, etc.)
2. Document your findings with specific paths, links, and references
3. Provide actionable insights that weren't apparent in the initial attempts
4. Focus on discovering NEW information that could lead to a breakthrough
5. Be systematic and comprehensive in your research approach

YOUR RESPONSE SHOULD INCLUDE:
- **Research Summary:** A comprehensive summary of your findings
- **Key Insights:** New insights that weren't apparent in previous attempts
- **Relevant Resources:** Specific paths, files, links, or references discovered
- **Recommended Approaches:** Specific strategies or solutions to try based on your research
- **Root Cause Hypotheses:** Updated theories about what might be causing the failure

Remember: The goal is to uncover information that will help {remaining_desc} succeed where the previous {agents_failed if agent_cycles else "agents"} failed. Be thorough and think outside the box!
"""

    return prompt


def conduct_research(state: ResearchState) -> ResearchState:
    """Conduct research on the test failure using available tools."""
    print("Conducting research on test failure...")

    # Build prompt for research
    prompt = build_research_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Research completed")

    # Parse response to extract resources (look for file paths, links, etc.)
    research_resources = []
    research_content = response.content

    # Simple heuristic to extract potential file paths and resources
    lines = research_content.split("\n")
    for line in lines:
        line = line.strip()
        # Look for file paths
        if (
            (
                "/" in line
                and (
                    ".py" in line
                    or ".java" in line
                    or ".cpp" in line
                    or ".h" in line
                    or ".js" in line
                )
            )
            or line.startswith("http")
            or "CL/" in line
            or "/google/" in line
        ):
            research_resources.append(line)

    return {
        **state,
        "research_summary": research_content,
        "research_resources": research_resources,
        "messages": messages + [response],
    }


def save_research(state: ResearchState) -> ResearchState:
    """Save the research findings to artifacts."""
    print("Saving research findings...")

    artifacts_dir = state["artifacts_dir"]
    cycle_number = state["cycle_number"]

    try:
        # Save research summary with cycle number
        research_summary_path = os.path.join(
            artifacts_dir, f"research_summary_cycle_{cycle_number}.md"
        )
        with open(research_summary_path, "w") as f:
            f.write(state["research_summary"])

        # Save research resources list with cycle number
        research_resources_path = os.path.join(
            artifacts_dir, f"research_resources_cycle_{cycle_number}.txt"
        )
        with open(research_resources_path, "w") as f:
            f.write(f"# Research Resources - Cycle {cycle_number}\n\n")
            for resource in state["research_resources"]:
                f.write(f"- {resource}\n")

        print(f"Research summary saved to: {research_summary_path}")
        print(f"Research resources saved to: {research_resources_path}")

        # Print summary for immediate viewing
        print("\n" + "=" * 80)
        print("RESEARCH FINDINGS SUMMARY:")
        print("=" * 80)
        print(state["research_summary"])
        if state["research_resources"]:
            print("\nRESOURCES DISCOVERED:")
            for resource in state["research_resources"]:
                print(f"- {resource}")
        print("=" * 80 + "\n")

        return {**state, "research_saved": True}

    except Exception as e:
        print(f"Error saving research findings: {e}")
        return {**state, "research_saved": False, "failure_reason": str(e)}


def handle_research_success(state: ResearchState) -> ResearchState:
    """Handle successful research completion."""
    print(
        f"""
🔍 Research completed successfully!

Research summary saved in: {state['artifacts_dir']}/research_summary.md
Research resources saved in: {state['artifacts_dir']}/research_resources.txt

The research findings will now be provided to the remaining agents to help them succeed.
"""
    )

    return state


def handle_research_failure(state: ResearchState) -> ResearchState:
    """Handle research failure."""
    print(
        f"""
❌ Failed to complete research.

Error: {state.get('failure_reason', 'Unknown error')}
Artifacts directory: {state['artifacts_dir']}
"""
    )

    return state


class FailedTestResearchWorkflow(BaseWorkflow):
    """A workflow for conducting research on failed test fixes."""

    def __init__(
        self,
        artifacts_dir: str,
        current_cycle_artifacts: List[str] = None,
        previous_research_cycles: List[List[str]] = None,
        agent_cycles: List[int] = None,
        current_cycle: int = None,
    ):
        self.artifacts_dir = artifacts_dir
        self.current_cycle_artifacts = current_cycle_artifacts or []
        self.previous_research_cycles = previous_research_cycles or []
        self.agent_cycles = agent_cycles or []
        self.current_cycle = current_cycle

    @property
    def name(self) -> str:
        return "failed-test-research"

    @property
    def description(self) -> str:
        return "Conduct research on failed test fixes to discover new resources and insights"

    def create_workflow(self):
        """Create and return the LangGraph workflow."""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("conduct_research", conduct_research)
        workflow.add_node("save_research", save_research)
        workflow.add_node("success", handle_research_success)
        workflow.add_node("failure", handle_research_failure)

        # Add edges
        workflow.add_edge(START, "conduct_research")
        workflow.add_edge("conduct_research", "save_research")

        # Add conditional edge based on save success
        workflow.add_conditional_edges(
            "save_research",
            lambda state: "success" if state["research_saved"] else "failure",
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

        initial_state: ResearchState = {
            "artifacts_dir": self.artifacts_dir,
            "research_summary": "",
            "research_resources": [],
            "research_saved": False,
            "failure_reason": None,
            "messages": [],
            "current_cycle_artifacts": self.current_cycle_artifacts,
            "previous_research_cycles": self.previous_research_cycles,
            "cycle_number": len(self.previous_research_cycles) + 1,
            "agent_cycles": self.agent_cycles,
            "current_cycle": self.current_cycle,
        }

        try:
            final_state = app.invoke(initial_state)
            return final_state["research_saved"]
        except Exception as e:
            print(f"Error running research workflow: {e}")
            return False
