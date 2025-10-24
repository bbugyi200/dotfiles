import os
import sys
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from shared_utils import run_shell_command

from .blackboard import BlackboardManager


def create_output_file(blackboard_dir: str, filename: str, content: str) -> str:
    """Create an output file and return its path."""
    file_path = os.path.join(blackboard_dir, filename)
    with open(file_path, "w") as f:
        f.write(content)
    return file_path


def get_cl_context_files(blackboard_dir: str) -> tuple[str, str]:
    """Get CL context information and save to files, returning file paths."""
    # Get hdesc output
    hdesc_result = run_shell_command("hdesc", capture_output=True)
    if hdesc_result.returncode == 0:
        hdesc_content = hdesc_result.stdout.strip()
    else:
        hdesc_content = f"Error running hdesc: {hdesc_result.stderr}"
    
    # Get branch_diff output
    branch_diff_result = run_shell_command("branch_diff", capture_output=True)
    if branch_diff_result.returncode == 0:
        branch_diff_content = branch_diff_result.stdout.strip()
    else:
        branch_diff_content = f"Error running branch_diff: {branch_diff_result.stderr}"
    
    # Create output files
    hdesc_file = create_output_file(blackboard_dir, "hdesc_output.txt", hdesc_content)
    branch_diff_file = create_output_file(blackboard_dir, "branch_diff_output.txt", branch_diff_content)
    
    return hdesc_file, branch_diff_file





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
        blackboard_dir = self.blackboard_manager.blackboard_dir
        
        # Create output files for all tool outputs
        hdesc_file, branch_diff_file = get_cl_context_files(blackboard_dir)
        
        # Get all existing blackboard content
        blackboards = self.blackboard_manager.get_all_blackboard_content()

        prompt = f"""# PLANNING AGENT - ITERATION {self.iteration}

## HEADER
You are the Planning Agent in a test-fixing workflow. Your role is to analyze the current situation and decide the next action to take.

Current Iteration: {self.iteration}
Test Command: {self.test_cmd}
Test Output File: @{self.test_output_file}

## CL CONTEXT
- CL Description: @{hdesc_file}
- Branch Diff: @{branch_diff_file}"""

        # Add blackboard content references
        planning_blackboard_path = self.blackboard_manager.get_planning_blackboard_path()
        editor_blackboard_path = self.blackboard_manager.get_editor_blackboard_path()
        research_blackboard_path = self.blackboard_manager.get_research_blackboard_path()
        
        if blackboards["planning"]:
            prompt += f"""

## PREVIOUS PLANNING BLACKBOARD
@{planning_blackboard_path}"""

        if blackboards["editor"]:
            prompt += f"""

## EDITOR BLACKBOARD
@{editor_blackboard_path}"""

        if blackboards["research"]:
            prompt += f"""

## RESEARCH BLACKBOARD
@{research_blackboard_path}"""

        if not any(blackboards.values()):
            prompt += "\n\n## PREVIOUS WORK\n(No previous work found - this is the first iteration)"

        prompt += """

## USER PROMPT #1 (PLANNING REQUEST)
Analyze the test failure and previous work (if any), then decide on the next action using the following STRUCTURED RESPONSE FORMAT:

DECISION: [Choose EXACTLY ONE: new_editor | next_editor | research | stop]
CONTENT:
[Provide detailed content for your chosen decision - this will be used as the prompt for the next agent]

DECISION OPTIONS:

1. **new_editor** - Start fresh with a new editor agent
   - Use when previous editor work failed or went wrong direction
   - Use for first editor attempt in this workflow run
   - Content should be a detailed prompt explaining what to fix

2. **next_editor** - Continue with existing editor work
   - Use when previous editor was on right track but needs to continue
   - Editor will have access to all previous editor blackboard content
   - Content should build on previous editor work

3. **research** - Gather more information first
   - Use when you need more information to proceed with code changes
   - Research agent can do code/bug/CL/Moma searches
   - Content should specify what to investigate

4. **stop** - Stop the workflow (last resort)
   - Use only when you cannot determine how to proceed
   - Prefer this over repeating failed approaches
   - Content should explain why stopping and what might be needed

DECISION CRITERIA:
- If iteration 1 or previous editor work failed completely: choose new_editor
- If previous editor work was partially successful: choose next_editor  
- If you need more information about the codebase/dependencies: choose research
- If you've tried multiple approaches and are stuck: choose stop

RESPONSE FORMAT EXAMPLE:
DECISION: new_editor
CONTENT:
The test is failing due to a Dart compilation error at line 575. The error indicates a missing variable declaration keyword. Please:
1. Read the file contentads/drx/fe/client/trafficking/shared/service/testing/lib/deal_check_test_data.dart
2. Fix the syntax error around line 575 by adding proper variable declaration
3. Save your changes - the workflow will automatically run tests after you finish

IMPORTANT:
- Follow the EXACT format above: DECISION: [choice] followed by CONTENT: [details]
- Make your content detailed and actionable
- Consider what has been tried before to avoid loops
- Your response will be parsed automatically - format matters!

Remember: You are planning and deciding, not fixing directly. The agents will execute your plan.
"""

        return prompt

    def run(self) -> Dict:
        """Run the planning agent."""
        print("Running Planning Agent...")

        # Build and send prompt
        prompt = self.build_prompt()
        messages = [HumanMessage(content=prompt)]
        response = self.model.invoke(messages)

        # Save the planning agent's response to blackboard using new format
        self.blackboard_manager.add_planning_entry(prompt, response.content)

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
        blackboard_dir = self.blackboard_manager.blackboard_dir
        
        # Create output files for all tool outputs
        hdesc_file, branch_diff_file = get_cl_context_files(blackboard_dir)

        session_type = "NEW SESSION" if self.is_new_session else "CONTINUATION SESSION"

        # Build the header with context and restrictions
        prompt = f"""# EDITOR AGENT - {session_type}

## HEADER
You are the Editor Agent in a test-fixing workflow. Your role is to make targeted code changes to fix the failing test.

Test Command: {self.test_cmd}
Test Output File: @{self.test_output_file}

RESTRICTIONS:
- You may ONLY modify code files that are directly related to the failing test
- You may ONLY make changes that are necessary to fix the test failure
- Do NOT make unrelated refactoring or cleanup changes
- Do NOT run any test commands (gai_test, pytest, etc.) - the workflow handles testing
- Focus on minimal, targeted fixes

## CL CONTEXT
- CL Description: @{hdesc_file}
- Branch Diff: @{branch_diff_file}"""

        # Add previous editor blackboard if this is not a new session
        if not self.is_new_session:
            editor_blackboard_path = self.blackboard_manager.get_editor_blackboard_path()
            previous_editor_work = self.blackboard_manager.read_editor_blackboard()
            if previous_editor_work:
                prompt += f"""

## EDITOR BLACKBOARD (PREVIOUS WORK)
@{editor_blackboard_path}

IMPORTANT: Build upon the previous work above. The planning agent has given you specific instructions on how to continue."""

        prompt += f"""

## USER PROMPT #1 (PLANNING INSTRUCTIONS)
{planning_prompt}

## USER PROMPT #2 (EDITOR TASK)
1. Analyze the test failure and understand what needs to be fixed
2. Make the necessary code changes using appropriate tools (Edit, Write, etc.)
3. Explain your reasoning for each change
4. IMPORTANT: Do NOT run any tests - the workflow will automatically run tests after you finish

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

        # Save the editor agent's response to blackboard using new format
        self.blackboard_manager.add_editor_entry(full_prompt, response.content)

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
        blackboard_dir = self.blackboard_manager.blackboard_dir
        
        # Create output files for all tool outputs
        hdesc_file, branch_diff_file = get_cl_context_files(blackboard_dir)

        # Build the header with capabilities
        prompt = f"""# RESEARCH AGENT

## HEADER
You are the Research Agent in a test-fixing workflow. Your role is to gather information and insights that will help fix the failing test.

Test Command: {self.test_cmd}
Test Output File: @{self.test_output_file}

AVAILABLE RESEARCH TOOLS:
- Code search (Grep, Glob tools) - Find relevant code patterns, functions, classes
- Bug search - Look for similar issues or known bugs
- CL search - Find related code changes or reviews
- Moma search - Search internal documentation and knowledge base
- Web search - Find external resources, documentation, or similar issues
- File analysis - Read and analyze relevant source files

## CL CONTEXT
- CL Description: @{hdesc_file}
- Branch Diff: @{branch_diff_file}"""

        # Add previous research blackboard
        research_blackboard_path = self.blackboard_manager.get_research_blackboard_path()
        previous_research = self.blackboard_manager.read_research_blackboard()
        if previous_research:
            prompt += f"""

## RESEARCH BLACKBOARD (PREVIOUS FINDINGS)
@{research_blackboard_path}

IMPORTANT: Build upon the previous research above. The planning agent has given you specific additional research to conduct."""
        else:
            prompt += """

## PREVIOUS RESEARCH
(This is the first research session for this test failure)"""

        prompt += f"""

## USER PROMPT #1 (PLANNING RESEARCH REQUEST)
{planning_prompt}

## USER PROMPT #2 (RESEARCH TASK)
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

        # Save the research agent's response to blackboard using new format
        self.blackboard_manager.add_research_entry(full_prompt, response.content)

        print("Research agent completed")
        print(f"Research agent findings:\n{response.content}")

        return {"messages": [response]}
