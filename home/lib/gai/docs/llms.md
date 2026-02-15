# LLM Provider Integration

This document describes the LLM provider abstraction layer in gai. The system supports pluggable LLM backends (currently
Claude Code and Gemini CLI) behind a shared orchestration layer that handles preprocessing, invocation, and
postprocessing.

## Table of Contents

- [Overview](#overview)
- [Provider Architecture](#provider-architecture)
- [Claude Code Integration](#claude-code-integration)
- [Gemini CLI Integration](#gemini-cli-integration)
- [Configuration](#configuration)
- [Model Tier System](#model-tier-system)
- [Environment Variables](#environment-variables)
- [CLI Flags](#cli-flags)
- [Prompt Preprocessing Pipeline](#prompt-preprocessing-pipeline)
- [Subprocess Streaming](#subprocess-streaming)
- [Postprocessing](#postprocessing)
- [Chat History](#chat-history)
- [Invocation Lifecycle](#invocation-lifecycle)

## Overview

The LLM provider layer decouples prompt handling from the underlying LLM backend. All providers share a common
preprocessing pipeline, subprocess streaming mechanism, and postprocessing workflow. The actual LLM invocation is
delegated to a pluggable provider selected at runtime.

Key design principles:

- **Providers are thin**: They only construct CLI commands and run subprocesses. All preprocessing and postprocessing
  lives in the shared orchestration layer.
- **Registry-based selection**: Providers register themselves by name and are resolved via config or explicit override.
- **Tier-based model selection**: Callers request a "large" or "small" tier; the provider maps it to a concrete model.

### Source Layout

| File                                 | Purpose                             |
| ------------------------------------ | ----------------------------------- |
| `src/llm_provider/__init__.py`       | Public API exports                  |
| `src/llm_provider/base.py`           | `LLMProvider` abstract base class   |
| `src/llm_provider/claude.py`         | Claude Code provider implementation |
| `src/llm_provider/gemini.py`         | Gemini CLI provider implementation  |
| `src/llm_provider/registry.py`       | Provider registration and lookup    |
| `src/llm_provider/config.py`         | Config file reader (`gai.yml`)      |
| `src/llm_provider/types.py`          | `ModelTier`, `LoggingContext` types |
| `src/llm_provider/_invoke.py`        | `invoke_agent()` orchestrator       |
| `src/llm_provider/_subprocess.py`    | `stream_process_output()`           |
| `src/llm_provider/preprocessing.py`  | 6-step preprocessing pipeline       |
| `src/llm_provider/postprocessing.py` | Logging, chat history, audio        |

## Provider Architecture

### Base Class

All providers implement the `LLMProvider` abstract base class:

```python
class LLMProvider(ABC):
    @abstractmethod
    def invoke(
        self,
        prompt: str,
        *,
        model_tier: ModelTier,
        suppress_output: bool = False,
    ) -> str: ...
```

| Parameter         | Type        | Description                                  |
| ----------------- | ----------- | -------------------------------------------- |
| `prompt`          | `str`       | Already-preprocessed prompt text             |
| `model_tier`      | `ModelTier` | `"large"` or `"small"`                       |
| `suppress_output` | `bool`      | If `True`, suppress real-time console output |

Returns the raw response text. Raises `subprocess.CalledProcessError` on failure.

### Registry

Providers are registered by name in a global registry (`registry.py`). Built-in providers are auto-registered on module
import:

```python
register_provider("claude", ClaudeCodeProvider)
register_provider("gemini", GeminiProvider)
```

To get a provider instance:

```python
provider = get_provider()          # Uses default from config
provider = get_provider("claude")  # Explicit provider name
```

### Selection Logic

1. If `provider_name` is passed to `invoke_agent()`, use that.
2. Otherwise, read the `llm_provider.provider` field from `~/.config/gai/gai.yml`.
3. If no config exists, fall back to `"gemini"`.

## Claude Code Integration

The `ClaudeCodeProvider` invokes the `claude` CLI tool.

### Command Construction

```
claude -p --model <alias> --output-format text --dangerously-skip-permissions [extra_args...]
```

The prompt is written to stdin, and output is streamed from stdout in real-time.

### Model Mapping

| Tier    | Claude CLI Alias |
| ------- | ---------------- |
| `large` | `opus`           |
| `small` | `sonnet`         |

### Environment Variables

| Variable                | Description                                                |
| ----------------------- | ---------------------------------------------------------- |
| `GAI_LLM_LARGE_ARGS`    | Extra CLI args for `large` tier (generic, preferred)       |
| `GAI_LLM_SMALL_ARGS`    | Extra CLI args for `small` tier (generic, preferred)       |
| `GAI_CLAUDE_LARGE_ARGS` | Extra CLI args for `large` tier (Claude-specific fallback) |
| `GAI_CLAUDE_SMALL_ARGS` | Extra CLI args for `small` tier (Claude-specific fallback) |

The generic `GAI_LLM_*_ARGS` variables take precedence. Values are split on whitespace and appended to the command.

### Timer Display

While waiting for a response, a `gemini_timer("Waiting for Claude")` spinner is shown (unless `suppress_output` is
`True`).

## Gemini CLI Integration

The `GeminiProvider` invokes Google's internal Gemini CLI tool.

### Command Construction

```
/google/bin/releases/gemini-cli/tools/gemini --yolo [extra_args...]
```

The prompt is written to stdin, and output is streamed from stdout in real-time.

### Model Mapping

Gemini does not have a built-in tier-to-model mapping in the provider code. Model selection is controlled entirely via
the extra args environment variables.

### Environment Variables

| Variable                 | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `GAI_LLM_LARGE_ARGS`     | Extra CLI args for `large` tier (generic, preferred)       |
| `GAI_LLM_SMALL_ARGS`     | Extra CLI args for `small` tier (generic, preferred)       |
| `GAI_BIG_GEMINI_ARGS`    | Extra CLI args for `large` tier (Gemini-specific fallback) |
| `GAI_LITTLE_GEMINI_ARGS` | Extra CLI args for `small` tier (Gemini-specific fallback) |

### Timer Display

While waiting for a response, a `gemini_timer("Waiting for Gemini")` spinner is shown (unless `suppress_output` is
`True`).

## Configuration

The LLM provider reads its configuration from `~/.config/gai/gai.yml` under the `llm_provider` key.

### Config File

```yaml
llm_provider:
  provider: claude # or "gemini" (default)
  model_tier_map:
    large: opus
    small: sonnet
```

### JSON Schema

The config is validated against `gai.schema.json`:

```json
{
  "llm_provider": {
    "type": "object",
    "properties": {
      "provider": {
        "type": "string",
        "description": "Name of the LLM provider to use (e.g., 'gemini', 'claude')",
        "default": "gemini"
      },
      "model_tier_map": {
        "type": "object",
        "properties": {
          "large": { "type": "string" },
          "small": { "type": "string" }
        }
      }
    }
  }
}
```

### Config Fields

| Field                               | Type   | Default    | Description                           |
| ----------------------------------- | ------ | ---------- | ------------------------------------- |
| `llm_provider.provider`             | string | `"gemini"` | Which registered provider to use      |
| `llm_provider.model_tier_map.large` | string | -          | Model identifier for the `large` tier |
| `llm_provider.model_tier_map.small` | string | -          | Model identifier for the `small` tier |

## Model Tier System

The model tier system abstracts away specific model names. Callers request either `"large"` (most capable) or `"small"`
(faster/cheaper), and the provider maps the tier to a concrete model.

### Type Definition

```python
ModelTier = Literal["large", "small"]
```

### Legacy Mapping

The old `"big"`/`"little"` terminology is still supported for backward compatibility:

| Old Value  | New Tier  | Display Label |
| ---------- | --------- | ------------- |
| `"big"`    | `"large"` | `BIG`         |
| `"little"` | `"small"` | `LITTLE`      |

The `model_size` parameter on `invoke_agent()` is deprecated. Use `model_tier` instead.

### Global Override

The model tier can be overridden globally via environment variable or CLI flag. The override forces ALL invocations to
use the specified tier regardless of what the caller requests.

**Resolution order:**

1. `GAI_MODEL_TIER_OVERRIDE` env var (accepts `"large"`, `"small"`, `"big"`, `"little"`)
2. `GAI_MODEL_SIZE_OVERRIDE` env var (legacy, same values)
3. `--model-tier` / `--model-size` CLI flag (sets the env var)
4. Caller's `model_tier` parameter (default: `"large"`)

## Environment Variables

Complete reference of environment variables used by the LLM provider layer.

### Generic (Provider-Agnostic)

| Variable                  | Description                                    |
| ------------------------- | ---------------------------------------------- |
| `GAI_LLM_LARGE_ARGS`      | Extra CLI args for `large` tier invocations    |
| `GAI_LLM_SMALL_ARGS`      | Extra CLI args for `small` tier invocations    |
| `GAI_MODEL_TIER_OVERRIDE` | Force all invocations to a specific model tier |
| `GAI_MODEL_SIZE_OVERRIDE` | Legacy alias for `GAI_MODEL_TIER_OVERRIDE`     |

### Claude-Specific

| Variable                | Description                                 |
| ----------------------- | ------------------------------------------- |
| `GAI_CLAUDE_LARGE_ARGS` | Claude-specific extra args for `large` tier |
| `GAI_CLAUDE_SMALL_ARGS` | Claude-specific extra args for `small` tier |

### Gemini-Specific

| Variable                 | Description                                          |
| ------------------------ | ---------------------------------------------------- |
| `GAI_BIG_GEMINI_ARGS`    | Gemini-specific extra args for `large` tier (legacy) |
| `GAI_LITTLE_GEMINI_ARGS` | Gemini-specific extra args for `small` tier (legacy) |

### VCS Provider

| Variable           | Description                                          |
| ------------------ | ---------------------------------------------------- |
| `GAI_VCS_PROVIDER` | Override VCS provider (`"git"`, `"hg"`, or `"auto"`) |

## CLI Flags

### ace

| Flag               | Values              | Description                                 |
| ------------------ | ------------------- | ------------------------------------------- |
| `-m, --model-tier` | `large`, `small`    | Override model tier for all LLM invocations |
| `--model-size`     | `big`, `little`     | Deprecated alias for `--model-tier`         |
| `--vcs-provider`   | `git`, `hg`, `auto` | Override VCS provider                       |

### axe

| Flag             | Values              | Description           |
| ---------------- | ------------------- | --------------------- |
| `--vcs-provider` | `git`, `hg`, `auto` | Override VCS provider |

The `ace` command wires `--model-tier` / `--model-size` into the `model_tier_override` parameter of `AceApp`. The
`--vcs-provider` flag is wired to the `GAI_VCS_PROVIDER` environment variable for downstream resolution.

## Prompt Preprocessing Pipeline

Before any prompt reaches a provider, it passes through a 6-step preprocessing pipeline defined in `preprocessing.py`.

### Steps

| #   | Step                 | Syntax         | Description                                        |
| --- | -------------------- | -------------- | -------------------------------------------------- |
| 1   | xprompt references   | `#name`        | Expand reusable prompt snippets from xprompts      |
| 2   | Command substitution | `$(cmd)`       | Execute shell commands and inline their output     |
| 3   | File references      | `@path`        | Inline file contents (copy absolute/tilde paths)   |
| 4   | Jinja2 rendering     | `{{ var }}`    | Render Jinja2 templates after all prior expansions |
| 5   | Prettier formatting  | -              | Format with prettier for consistent markdown       |
| 6   | Comment stripping    | `<!-- ... -->` | Remove HTML/markdown comments                      |

### Order Matters

The pipeline runs in strict order. Jinja2 rendering (step 4) happens **after** xprompt, command substitution, and file
reference expansion, so templates can reference content injected by earlier steps.

### Home Mode

When `is_home_mode=True`, file reference processing skips copying files (step 3). This is used when the invocation
doesn't need side effects from `@path` references.

### Source Functions

The preprocessing steps delegate to functions from two libraries:

- **`xprompt`**: `process_xprompt_references()`, `is_jinja2_template()`, `render_toplevel_jinja2()`
- **`gemini_wrapper.file_references`**: `process_command_substitution()`, `process_file_references()`,
  `format_with_prettier()`, `strip_html_comments()`

## Subprocess Streaming

Both providers use the shared `stream_process_output()` function from `_subprocess.py` to stream LLM output in
real-time.

### Mechanism

1. The provider spawns the CLI tool via `subprocess.Popen` with `stdin=PIPE`, `stdout=PIPE`, `stderr=PIPE`.
2. The prompt is written to stdin, then stdin is closed.
3. Both stdout and stderr file descriptors are set to **non-blocking** mode via `os.set_blocking()`.
4. A `select.select()` loop with a 0.1s timeout polls for readable data on both streams.
5. Lines are read and optionally printed to the console in real-time.
6. After the process exits (`process.poll() is not None`), any remaining buffered output is drained.
7. The function returns `(stdout_content, stderr_content, return_code)`.

### Output Suppression

When `suppress_output=True`, lines are still captured but not printed to the console. This is used for background
invocations where the caller only needs the final result.

## Postprocessing

After a provider returns (or raises an error), the orchestration layer runs postprocessing steps.

### On Success (`postprocess_success`)

1. **Audio notification**: Plays a sound via `run_bam_command("Agent reply received")` (skipped if `suppress_output`).
2. **Log to gai.md**: Appends a timestamped entry with the prompt and response to `<artifacts_dir>/gai.md` (if
   `artifacts_dir` is set).
3. **Save chat history**: Writes to `~/.gai/chats/` if `workflow` is set. See [Chat History](#chat-history).

### On Error (`postprocess_error`)

1. **Rich error display**: Prints the prompt and error via `print_prompt_and_response()` with an `_ERROR` suffix on the
   agent type label (skipped if `suppress_output`).
2. **Log to gai.md**: Same as success, but the response is the error message and the agent type gets an `_ERROR` suffix.
3. **Save error chat history**: Writes to `~/.gai/chats/` with an `_ERROR` agent suffix.

### gai.md Log Format

Each entry in the log file follows this format:

```markdown
## <timestamp> - <agent_type> - iteration <N> - tag <workflow_tag>

### PROMPT:

\`\`\` <prompt text> \`\`\`

### RESPONSE:

\`\`\` <response text> \`\`\`

---
```

### Prompt File Saving

Before invocation, the preprocessed prompt is saved to `<artifacts_dir>/<agent_type>_prompt.md` (or
`<agent_type>_iter_<N>_prompt.md` if an iteration number is set). This allows reviewing the exact prompt that was sent.

## Chat History

Chat histories are stored as markdown files in `~/.gai/chats/`.

### File Naming

```
<branch_or_workspace>-<workflow>-[<agent>-]<timestamp>.md
```

| Part                  | Source                                   | Example             |
| --------------------- | ---------------------------------------- | ------------------- |
| `branch_or_workspace` | Output of `branch_or_workspace_name`     | `my_feature`        |
| `workflow`            | Workflow name, normalized                | `crs`, `run`        |
| `agent`               | Agent type (omitted if same as workflow) | `editor`, `planner` |
| `timestamp`           | `YYmmdd_HHMMSS` format                   | `260214_153042`     |

Dashes and slashes in workflow names are normalized to underscores.

### File Format

```markdown
# Chat History - <workflow> (<agent>)

**Timestamp:** <display_timestamp>

## Previous Conversation

<previous history if resuming>

---

## Prompt

<prompt text>

## Response

<response text>
```

### Resume Support

The `gai run --resume` flag loads a previous chat history file and prepends it to the new conversation. The
`load_chat_history()` function supports both basenames and full paths, with an option to increment markdown heading
levels for nesting.

## Invocation Lifecycle

The `invoke_agent()` function in `_invoke.py` orchestrates the complete lifecycle of an LLM invocation. Here is the
end-to-end flow:

```
invoke_agent(prompt, agent_type, model_tier, ...)
│
├── 1. Handle deprecated model_size → model_tier mapping
├── 2. Check GAI_MODEL_TIER_OVERRIDE / GAI_MODEL_SIZE_OVERRIDE env vars
├── 3. Build LoggingContext from parameters
│
├── 4. Preprocess prompt (6-step pipeline)
│   ├── xprompt references (#name)
│   ├── Command substitution ($(cmd))
│   ├── File references (@path)
│   ├── Jinja2 rendering ({{ var }})
│   ├── Prettier formatting
│   └── Comment stripping
│
├── 5. Display decision counts (if not suppressed)
├── 6. Print prompt via Rich (if not suppressed)
├── 7. Generate or use provided timestamp
├── 8. Save prompt to artifacts directory
│
├── 9. Get provider from registry and invoke
│   ├── Build CLI command with flags
│   ├── Spawn subprocess (Popen)
│   ├── Write prompt to stdin
│   └── Stream stdout/stderr in real-time
│
├── 10. Postprocess
│   ├── Success path:
│   │   ├── Audio notification
│   │   ├── Log to gai.md
│   │   └── Save chat history
│   └── Error path:
│       ├── Rich error display
│       ├── Log error to gai.md
│       └── Save error chat history
│
└── 11. Return AIMessage(content=response)
```

### Parameters

| Parameter         | Type                        | Default    | Description                             |
| ----------------- | --------------------------- | ---------- | --------------------------------------- |
| `prompt`          | `str`                       | (required) | Raw prompt to send                      |
| `agent_type`      | `str`                       | (required) | Agent type label (e.g., `"editor"`)     |
| `model_tier`      | `ModelTier`                 | `"large"`  | Model tier to use                       |
| `model_size`      | `"big" \| "little" \| None` | `None`     | Deprecated, use `model_tier`            |
| `iteration`       | `int \| None`               | `None`     | Iteration number for logging            |
| `workflow_tag`    | `str \| None`               | `None`     | Workflow tag for logging                |
| `artifacts_dir`   | `str \| None`               | `None`     | Directory for gai.md and prompt files   |
| `workflow`        | `str \| None`               | `None`     | Workflow name for chat history          |
| `suppress_output` | `bool`                      | `False`    | Suppress console output                 |
| `timestamp`       | `str \| None`               | `None`     | Shared timestamp (`YYmmdd_HHMMSS`)      |
| `is_home_mode`    | `bool`                      | `False`    | Skip file copying for `@` references    |
| `decision_counts` | `dict[str, Any] \| None`    | `None`     | Planning agent decision counts          |
| `provider_name`   | `str \| None`               | `None`     | Override provider (default from config) |

### Return Value

Always returns an `AIMessage` (from `langchain_core.messages`). On error, the `content` field contains the error message
rather than a response.
