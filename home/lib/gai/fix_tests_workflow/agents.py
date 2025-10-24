import os
import sys
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage

from .blackboard import BlackboardManager


class BaseAgent:
    """Base class for all agents in the fix-tests workflow."""

    def __init__(
        self,
        blackboard_manager: BlackboardManager,
        test_cmd: str,
        test_output_file: str,
    ):
        self.blackboard_manager = blackboard_manager
        self.test_cmd = test_cmd
        self.test_output_file = test_output_file
        self.model = GeminiCommandWrapper()

    def read_test_output(self) -> str:
        """Read the test output file content."""
        try:
            with open(self.test_output_file, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading test output file {self.test_output_file}: {str(e)}"


class PlanningAgent(BaseAgent):
    """Planning agent that decides the next action in the workflow."""

    def __init__(
        self,
        blackboard_manager: BlackboardManager,
        test_cmd: str,
        test_output_file: str,
        iteration: int,
    ):
        super().__init__(blackboard_manager, test_cmd, test_output_file)
        self.iteration = iteration

    def build_prompt(self) -> str:
        """Build the prompt for the planning agent."""
        test_output = self.read_test_output()

        # Get all existing blackboard content
        blackboards = self.blackboard_manager.get_all_blackboard_content()

        prompt = f"""You are the Planning Agent in a test-fixing workflow. Your role is to analyze the current situation and decide the next action to take.

CURRENT SITUATION:
- Iteration: {self.iteration}
- Test Command: {self.test_cmd}
- Test Output File: {self.test_output_file}

TEST FAILURE OUTPUT:
```
{test_output}
```

PREVIOUS WORK (from blackboards):
"""

        if blackboards["planning"]:
            prompt += f"""
PLANNING HISTORY:
```
{blackboards["planning"]}
```
"""

        if blackboards["editor"]:
            prompt += f"""
EDITOR WORK:
```
{blackboards["editor"]}
```
"""

        if blackboards["research"]:
            prompt += f"""
RESEARCH FINDINGS:
```
{blackboards["research"]}
```
"""

        if not any(blackboards.values()):
            prompt += "\n(No previous work found - this is the first iteration)"

        prompt += f"""

YOUR TASK:
Analyze the test failure and previous work (if any), then decide on the next action by creating EXACTLY ONE of these files:

1. **bb/gai_fix_tests/new_editor_prompt.md** - Create this if you want to start fresh with a new editor agent
   - Use this when previous editor work was unsuccessful or went in the wrong direction
   - Use this for the first editor attempt in this workflow run
   - The file should contain a detailed prompt for the editor agent explaining what to fix

2. **bb/gai_fix_tests/next_editor_prompt.md** - Create this if you want to continue with the existing editor work
   - Use this when the previous editor was on the right track but needs to continue/refine
   - The editor will have access to all previous editor blackboard content
   - The file should contain a prompt building on the previous editor work

3. **bb/gai_fix_tests/next_research_prompt.md** - Create this if you need more information
   - Use this when you don't have enough information to proceed with code changes
   - The research agent can do code searches, bug searches, CL searches, Moma searches, etc.
   - The file should contain a specific research prompt about what to investigate

4. **bb/gai_fix_tests/stop_workflow.md** - Create this as a last resort
   - Use this only when you cannot determine how to proceed
   - Prefer this over continuing to retry failed approaches
   - The file should explain why the workflow should stop and what might be needed

DECISION CRITERIA:
- If this is iteration 1 or previous editor work failed completely: choose new_editor_prompt.md
- If previous editor work was partially successful: choose next_editor_prompt.md  
- If you need more information about the codebase, dependencies, or similar issues: choose next_research_prompt.md
- If you've tried multiple approaches and are stuck: choose stop_workflow.md

IMPORTANT INSTRUCTIONS:
- Create EXACTLY ONE file with your decision
- Make the prompt detailed and specific
- Consider what has already been tried to avoid repeating failed approaches
- Be decisive but thoughtful in your choice

Remember: Your job is to plan and decide, not to fix the test directly. The editor and research agents will execute your plan.
"""

        return prompt

    def run(self) -> Dict:
        """Run the planning agent."""
        print("Running Planning Agent...")

        # Build and send prompt
        prompt = self.build_prompt()
        messages = [HumanMessage(content=prompt)]
        response = self.model.invoke(messages)

        # Save the planning agent's response to blackboard
        planning_content = f"""
# Planning Agent - Iteration {self.iteration}

## Prompt Sent:
{prompt}

## Response:
{response.content}

---

"""

        # Write to a new planning blackboard file
        self.blackboard_manager.write_planning_blackboard(planning_content)

        print("Planning agent completed")
        print(f"Planning agent response:\n{response.content}")

        return {"messages": [response]}


class EditorAgent(BaseAgent):
    """Editor agent that makes code changes to fix tests."""

    def __init__(
        self,
        blackboard_manager: BlackboardManager,
        test_cmd: str,
        test_output_file: str,
        is_new_session: bool,
    ):
        super().__init__(blackboard_manager, test_cmd, test_output_file)
        self.is_new_session = is_new_session

    def build_prompt(self, planning_prompt: str) -> str:
        """Build the prompt for the editor agent."""
        test_output = self.read_test_output()

        # Build the header with context and restrictions
        prompt = f"""You are the Editor Agent in a test-fixing workflow. Your role is to make targeted code changes to fix the failing test.

RESTRICTIONS:
- You may ONLY modify code files that are directly related to the failing test
- You may ONLY make changes that are necessary to fix the test failure
- Do NOT make unrelated refactoring or cleanup changes
- Focus on minimal, targeted fixes

CURRENT SITUATION:
- Test Command: {self.test_cmd}
- Test Output File: {self.test_output_file}

TEST FAILURE OUTPUT:
```
{test_output}
```

PLANNING AGENT INSTRUCTIONS:
{planning_prompt}
"""

        # Add previous editor context if this is not a new session
        if not self.is_new_session:
            previous_editor_work = self.blackboard_manager.read_editor_blackboard()
            if previous_editor_work:
                prompt += f"""

PREVIOUS EDITOR WORK:
{previous_editor_work}

IMPORTANT: Build upon the previous work above. The planning agent has given you specific instructions on how to continue.
"""

        prompt += """

YOUR TASK:
1. Analyze the test failure and understand what needs to be fixed
2. Make the necessary code changes using appropriate tools (Edit, Write, etc.)
3. Explain your reasoning for each change
4. Test your changes if possible (but the workflow will run final tests)

APPROACH:
- Start by understanding the root cause of the test failure
- Make minimal, targeted changes to fix the specific issue
- Avoid broad changes that might introduce new problems
- Document your reasoning for each change

Remember: Focus on fixing this specific test failure, not general improvements to the codebase.
"""

        return prompt

    def run(self, planning_prompt: str) -> Dict:
        """Run the editor agent with the given planning prompt."""
        print("Running Editor Agent...")

        # Build the full prompt
        full_prompt = self.build_prompt(planning_prompt)

        # Send to model
        messages = [HumanMessage(content=full_prompt)]
        response = self.model.invoke(messages)

        # Prepare blackboard content
        blackboard_content = f"""
# Editor Agent Session - {"New" if self.is_new_session else "Continuation"}

## Planning Prompt:
{planning_prompt}

## Full Prompt Sent:
{full_prompt}

## Response:
{response.content}

---

"""

        # Write or append to editor blackboard
        if self.is_new_session:
            self.blackboard_manager.write_editor_blackboard(blackboard_content)
        else:
            self.blackboard_manager.append_editor_blackboard(blackboard_content)

        print("Editor agent completed")
        print(f"Editor agent response:\n{response.content}")

        return {"messages": [response]}


class ResearchAgent(BaseAgent):
    """Research agent that gathers information to help fix tests."""

    def __init__(
        self,
        blackboard_manager: BlackboardManager,
        test_cmd: str,
        test_output_file: str,
    ):
        super().__init__(blackboard_manager, test_cmd, test_output_file)

    def build_prompt(self, planning_prompt: str) -> str:
        """Build the prompt for the research agent."""
        test_output = self.read_test_output()

        # Build the header with capabilities
        prompt = f"""You are the Research Agent in a test-fixing workflow. Your role is to gather information and insights that will help fix the failing test.

AVAILABLE RESEARCH TOOLS:
- Code search (Grep, Glob tools) - Find relevant code patterns, functions, classes
- Bug search - Look for similar issues or known bugs
- CL search - Find related code changes or reviews
- Moma search - Search internal documentation and knowledge base
- Web search - Find external resources, documentation, or similar issues
- File analysis - Read and analyze relevant source files

CURRENT SITUATION:
- Test Command: {self.test_cmd}
- Test Output File: {self.test_output_file}

TEST FAILURE OUTPUT:
```
{test_output}
```

PLANNING AGENT RESEARCH REQUEST:
{planning_prompt}
"""

        # Add previous research context
        previous_research = self.blackboard_manager.read_research_blackboard()
        if previous_research:
            prompt += f"""

PREVIOUS RESEARCH FINDINGS:
{previous_research}

IMPORTANT: Build upon the previous research above. The planning agent has given you specific additional research to conduct.
"""
        else:
            prompt += """

FIRST RESEARCH SESSION: This is the first time research is being conducted for this test failure.
"""

        prompt += """

YOUR TASK:
1. Follow the specific research request from the planning agent
2. Use all available search and analysis tools to gather relevant information
3. Look for:
   - Similar test failures or error patterns
   - Related code that might be causing the issue
   - Recent changes that could have introduced the problem
   - Documentation or examples that might help
   - Known issues or workarounds
4. Provide actionable insights and recommendations
5. Document your findings clearly with specific references (file paths, links, etc.)

RESEARCH APPROACH:
- Start with the most specific searches related to the error message
- Expand to broader searches if needed
- Look for patterns in similar code or tests
- Check for recent changes that might be related
- Provide concrete next steps based on your findings

Remember: Your goal is to provide information that will help the editor agent make the right code changes.
"""

        return prompt

    def run(self, planning_prompt: str) -> Dict:
        """Run the research agent with the given planning prompt."""
        print("Running Research Agent...")

        # Build the full prompt
        full_prompt = self.build_prompt(planning_prompt)

        # Send to model
        messages = [HumanMessage(content=full_prompt)]
        response = self.model.invoke(messages)

        # Prepare blackboard content
        blackboard_content = f"""
# Research Agent Session

## Planning Prompt:
{planning_prompt}

## Full Prompt Sent:
{full_prompt}

## Findings:
{response.content}

---

"""

        # Write or append to research blackboard
        if not self.blackboard_manager.blackboard_exists("research"):
            # First research session - create with header
            header = """# Research Blackboard

This blackboard contains all research findings and insights gathered during the fix-tests workflow.

---

"""
            self.blackboard_manager.write_research_blackboard(
                header + blackboard_content
            )
        else:
            # Append to existing research
            self.blackboard_manager.append_research_blackboard(blackboard_content)

        print("Research agent completed")
        print(f"Research agent findings:\n{response.content}")

        return {"messages": [response]}
