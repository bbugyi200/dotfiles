# GAI Tool Calling System

## Overview

The GAI (Google AI LangGraph workflow) system now supports tool calling for API mode, allowing the Gemini API to perform file operations and shell commands that were previously only available in CLI mode.

## Architecture

### Key Components

1. **`api_tools.py`** - Defines LangGraph tools for file operations and shell commands
2. **`tool_calling_workflow.py`** - Implements the LangGraph workflow for tool calling 
3. **`gemini_wrapper.py`** - Updated to use tool calling when in API mode
4. **`gemini_api_client.py`** - Fixed to handle LangChain message types correctly

### Available Tools

- **`write_file`** - Write content to a file, creating directories as needed
- **`read_file`** - Read the contents of a file
- **`edit_file`** - Edit a file by replacing old content with new content
- **`append_to_file`** - Append content to a file
- **`run_shell_command`** - Execute shell commands with timeout (30s)
- **`list_directory`** - List directory contents with file/folder indicators
- **`file_exists`** - Check if a file or directory exists

## How It Works

### 1. Tool Call Format

When in API mode, agents can request tool usage with this format:

```
```tool_call
tool_name: write_file
file_path: /path/to/file.txt
content: Hello, world!
```
```

### 2. Workflow Process

1. **Enhanced Prompt**: The initial prompt is enhanced with tool descriptions and usage instructions
2. **API Call**: Gemini API is called with the enhanced prompt
3. **Tool Extraction**: Response is parsed for `tool_call` blocks using regex
4. **Tool Execution**: Extracted tools are executed locally 
5. **Result Feedback**: Tool results are fed back to the model
6. **Iteration**: Process repeats until final response (max 5 iterations)

### 3. Configuration

- **CLI Mode**: Always uses CLI tools directly (no change)
- **API Mode**: Uses tool calling workflow when `GAI_USE_GEMINI_API=true`
- **Fallback**: Falls back to direct API call if tool calling unavailable

## Usage

### Enable API Mode with Tools

```bash
export GAI_USE_GEMINI_API=true
```

### Agent Behavior

- **Planner Agent**: Uses API mode with tools (can edit files, run commands)
- **Other Agents**: Use CLI mode (editor, verification, research, etc.)

### Example Workflow

1. Planner agent receives prompt with tool descriptions
2. Agent responds with tool calls to read files, make edits, etc.
3. Tools execute locally and provide results
4. Agent continues based on results, making more tool calls if needed
5. Final response provided when task complete

## File Path Expansion

The system also supports automatic file path expansion for API mode:
- `@/path/to/file.txt` in prompts gets expanded to full file contents
- Clear delimiters show file boundaries in the prompt
- Works alongside tool calling for comprehensive file access

## Error Handling

- Tool execution errors are captured and fed back to the model
- 30-second timeout on shell commands prevents hanging
- Graceful fallback to direct API call if tool system fails
- Import errors handled with fallback behavior

## Testing

Run the tool calling tests:

```bash
cd ~/lib/gai
source venv/bin/activate  
python test_tool_calling.py  # Creates temp test if needed
```

## Future Enhancements

- Additional tools for git operations, dependency management
- Tool result caching for performance
- Enhanced error recovery and retry logic
- Tool usage analytics and optimization