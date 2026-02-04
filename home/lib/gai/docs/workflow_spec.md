# Workflow Specification

This document describes the YAML workflow format for gai xprompt workflows. Workflows enable multi-step agent pipelines
with control flow, parallel execution, and human-in-the-loop approval.

## Table of Contents

- [Top-Level Structure](#top-level-structure)
- [Input Parameters](#input-parameters)
- [Step Types](#step-types)
- [Output Specification](#output-specification)
- [Control Flow](#control-flow)
- [Parallel Execution](#parallel-execution)
- [Join Modes](#join-modes)
- [Template Syntax](#template-syntax)
- [Human-in-the-Loop](#human-in-the-loop)
- [Examples](#examples)

## Top-Level Structure

A workflow YAML file has three top-level fields:

```yaml
name: my_workflow # Workflow identifier (optional, defaults to filename)
input: # Input parameter definitions (optional)
  ...
steps: # Ordered list of steps (required)
  - ...
```

### Fields

| Field   | Required | Description                                                                               |
| ------- | -------- | ----------------------------------------------------------------------------------------- |
| `name`  | No       | Workflow identifier used in `#name(args)` syntax. Defaults to filename without extension. |
| `input` | No       | Input parameter definitions. See [Input Parameters](#input-parameters).                   |
| `steps` | Yes      | Ordered list of workflow steps to execute.                                                |

## Input Parameters

Workflows can declare typed input parameters that users provide when invoking the workflow.

### Longform Syntax

```yaml
input:
  - name: diff_path
    type: path
  - name: max_retries
    type: int
    default: 3
  - name: description
    type: text
    default: ""
```

### Shortform Syntax

```yaml
input:
  diff_path: path
  max_retries: { type: int, default: 3 }
  description: { type: text, default: "" }
```

Or even more concise for simple types:

```yaml
input: { diff_path: path, split_desc: { type: line, default: "multiple CLs" } }
```

### Supported Types

| Type    | Description                                         |
| ------- | --------------------------------------------------- |
| `word`  | Single word, no whitespace                          |
| `line`  | Single line, no newlines                            |
| `text`  | Multi-line text (any content)                       |
| `path`  | File path (no whitespace, must exist)               |
| `int`   | Integer value                                       |
| `bool`  | Boolean value (`true`/`false`, `yes`/`no`, `1`/`0`) |
| `float` | Floating point value                                |

### Default Values

Parameters without a `default` are required. Parameters with `default: null` or `default: ""` are optional.

## Step Types

Each step must have exactly one of these execution types:

### Prompt Steps

Execute an LLM prompt, optionally referencing xprompts:

```yaml
- name: generate_plan
  prompt: |
    #plan_generator(
      context="{{ previous_step.output }}",
      requirements="{{ requirements }}"
    )
  output: { plan: text, files: text }
```

The `prompt` field contains a prompt template that can:

- Reference xprompts using `#xprompt_name(args)` syntax
- Use Jinja2 template variables: `{{ variable }}`
- Include multi-line content

### Bash Steps

Execute a shell command:

```yaml
- name: get_status
  bash: git status --porcelain
  output: { files: text }
```

```yaml
- name: complex_script
  bash: |
    counter_file="/tmp/counter"
    if [ ! -f "$counter_file" ]; then echo "0" > "$counter_file"; fi
    count=$(cat "$counter_file")
    echo "count=$count"
  output: { count: int }
```

### Python Steps

Execute Python code:

```yaml
- name: process_data
  python: |
    import json
    data = json.loads('{{ input_json }}')
    result = [item.upper() for item in data]
    print("result=" + json.dumps(result))
  output: { result: text }
```

Python steps run in a subprocess with access to installed packages.

### Parallel Steps

Execute multiple nested steps concurrently:

```yaml
- name: fetch_all
  parallel:
    - name: fetch_users
      bash: curl -s https://api.example.com/users
      output: { users: text }
    - name: fetch_posts
      bash: curl -s https://api.example.com/posts
      output: { posts: text }
```

See [Parallel Execution](#parallel-execution) for details.

## Output Specification

Steps can declare an output schema for structured output parsing.

### Simple Object Format

```yaml
output: { field_name: type, another_field: type }
```

Example:

```yaml
- name: parse_config
  bash: echo "name=myapp\nversion=1.0"
  output: { name: word, version: word }
```

### Array Format

For steps that produce a list of objects:

```yaml
output: [{ name: word, description: text }]
```

Example:

```yaml
- name: generate_items
  prompt: Generate a list of items
  output: [{ name: word, description: text, priority: { type: int, default: 0 } }]
```

### Nested Defaults

Fields can have defaults using nested dict syntax:

```yaml
output:
  name: word
  parent: { type: word, default: "" }
  priority: { type: int, default: 0 }
```

### Output Parsing

Step output is parsed in this order:

1. **JSON**: If output is valid JSON, parse and validate against schema
2. **Key=Value**: Parse lines like `key=value` into a dict
3. **Text fallback**: Store raw output as `_raw` or `_output`

For bash/python steps, output should be printed as `key=value` lines:

```bash
echo "success=true"
echo "count=42"
echo "message=Operation completed"
```

## Control Flow

### Conditional Execution (`if`)

Skip a step if a condition is false:

```yaml
- name: optional_step
  bash: echo "This runs conditionally"
  if: "{{ run_optional }}"
```

```yaml
- name: skip_on_failure
  bash: echo "Only runs if previous succeeded"
  if: "{{ previous_step.success }}"
```

### For Loops (`for`)

Iterate over a list:

```yaml
# Single variable
- name: process_items
  bash: echo "Processing {{ item }}"
  for: { item: "{{ items }}" }
  output: { result: text }

# Multiple parallel variables (must have equal length)
- name: process_pairs
  bash: echo "{{ name }} has id {{ id }}"
  for:
    name: "{{ names }}"
    id: "{{ ids }}"
  output: { name: word, id: int }
```

The `for` field maps variable names to Jinja2 expressions that evaluate to lists. All lists must have equal length.

### While Loops (`while`)

Execute step while a condition is true (checked after each iteration):

```yaml
# Short form
- name: poll_status
  bash: |
    status=$(check_status)
    echo "pending=$status"
  while: "{{ poll_status.pending }}"
  output: { pending: bool }

# Long form with max iterations
- name: poll_with_limit
  bash: echo "active={{ check_active }}"
  while:
    condition: "{{ poll_with_limit.active }}"
    max: 10
  output: { active: bool }
```

The step runs at least once, then continues while the condition is true. Default max iterations: 100.

### Repeat/Until Loops (`repeat`)

Execute step until a condition becomes true (do-while semantics):

```yaml
- name: retry_operation
  bash: |
    result=$(attempt_operation)
    echo "success=$result"
  repeat:
    until: "{{ retry_operation.success }}"
    max: 5
  output: { success: bool }
```

The step runs at least once, then repeats until the `until` condition is true. Default max iterations: 100.

### Combined Control Flow

`if` can be combined with `for`:

```yaml
- name: conditional_loop
  bash: echo "Processing {{ item }}"
  if: "{{ should_process }}"
  for: { item: "{{ items }}" }
```

`for` can be combined with `parallel`:

```yaml
- name: parallel_per_item
  for: { item: "[1, 2, 3]" }
  parallel:
    - name: task_a
      bash: echo "A processing {{ item }}"
    - name: task_b
      bash: echo "B processing {{ item }}"
```

## Parallel Execution

The `parallel` field runs nested steps concurrently.

### Basic Usage

```yaml
- name: parallel_tasks
  parallel:
    - name: task_a
      bash: echo "result=done_a"
      output: { result: word }
    - name: task_b
      bash: echo "result=done_b"
      output: { result: word }
```

### Accessing Results

Default join mode is `object`, nesting results under step names:

```yaml
# After parallel_tasks completes:
{{ parallel_tasks.task_a.result }}  # "done_a"
{{ parallel_tasks.task_b.result }}  # "done_b"
```

### Nested Step Restrictions

Steps within `parallel` cannot have:

- `for`, `repeat`, or `while` loops
- Nested `parallel` blocks
- `hitl: true`

### Fail-Fast Behavior

By default (`fail_fast: true`), if any parallel step fails, remaining steps are cancelled.

## Join Modes

The `join` field controls how iteration/parallel results are combined.

| Mode     | Default For | Description                                   |
| -------- | ----------- | --------------------------------------------- |
| `array`  | `for` loops | Collect results as a list                     |
| `object` | `parallel`  | Merge results into a single object            |
| `text`   | -           | Concatenate results as newline-separated text |
| `lastOf` | -           | Keep only the last result                     |

### Examples

```yaml
# Array join (default for for:)
- name: collect_results
  bash: echo "value={{ item }}"
  for: { item: "[1, 2, 3]" }
  output: { value: int }
# Result: [{"value": 1}, {"value": 2}, {"value": 3}]

# Text join
- name: concatenate
  bash: echo "line={{ item }}"
  for: { item: "['a', 'b', 'c']" }
  join: text
  output: { line: word }
# Result: "line=a\nline=b\nline=c"

# lastOf join
- name: keep_last
  bash: echo "final={{ item }}"
  for: { item: "['first', 'middle', 'last']" }
  join: lastOf
  output: { final: word }
# Result: {"final": "last"}

# Object join (default for parallel:)
- name: merge_parallel
  parallel:
    - name: a
      bash: echo "key_a=value_a"
    - name: b
      bash: echo "key_b=value_b"
# Result: {"a": {"key_a": "value_a"}, "b": {"key_b": "value_b"}}
```

## Template Syntax

Workflows use Jinja2 for template rendering.

### Variable Access

```yaml
# Input parameters
{{ parameter_name }}

# Step outputs
{{ step_name.field }}
{{ step_name.nested.field }}

# Loop variables (within for: loops)
{{ item }}
{{ name }}
```

### Filters

```yaml
# Convert to JSON
{{ data | tojson }}

# Get length
{{ items | length }}
```

### Boolean Logic

```yaml
# Conditions
{{ value and other_value }}
{{ value or fallback }}
{{ not value }}

# Defined check
{{ variable is defined }}
```

### Conditionals in Templates

```yaml
prompt: |
  {% if condition %}
  Include this text
  {% endif %}

  {{ "yes" if flag else "no" }}
```

## Human-in-the-Loop

The `hitl: true` directive pauses execution for user approval.

### Basic Usage

```yaml
- name: generate_plan
  prompt: Generate a migration plan
  output: { plan: text }
  hitl: true
```

### Approval Flow

When a HITL step completes:

1. Step output is displayed to the user
2. User can:
   - **Accept**: Continue to next step
   - **Edit**: Modify the output before continuing
   - **Reject**: Abort the workflow
   - **Feedback** (prompt only): Provide feedback for regeneration
   - **Rerun** (bash/python only): Re-execute the command

### Accessing Approval Status

After a HITL step, `step.approved` indicates whether the user accepted:

```yaml
- name: prompt_user
  bash: echo "message=Continue with operation?"
  output: { message: text }
  hitl: true

- name: execute_if_approved
  if: "{{ prompt_user.approved }}"
  bash: perform_operation
```

### Restrictions

- HITL steps cannot be nested within `parallel` blocks
- HITL works with `prompt`, `bash`, and `python` step types

## Examples

### Complete Workflow Files

The following workflow files demonstrate these features:

- `eval_ifs_loops.yml` - Conditional execution, for loops, while/repeat loops
- `eval_parallel.yml` - Parallel execution with different join modes
- `split.yml` - Real workflow with HITL, prompt steps, and xprompt references

### Minimal Example

```yaml
name: simple_workflow
input: { name: word }
steps:
  - name: greet
    bash: echo "message=Hello, {{ name }}!"
    output: { message: line }
```

### Multi-Step with Conditionals

```yaml
name: conditional_workflow
input:
  run_optional: { type: bool, default: true }
  items: { type: text, default: '["a", "b", "c"]' }

steps:
  - name: setup
    bash: echo "ready=true"
    output: { ready: bool }

  - name: process_items
    bash: echo "processed={{ item }}"
    if: "{{ setup.ready }}"
    for: { item: "{{ items }}" }
    output: { processed: word }

  - name: optional_step
    bash: echo "ran=true"
    if: "{{ run_optional }}"
    output: { ran: bool }

  - name: summary
    bash: echo "items_count={{ process_items | length }}"
    output: { items_count: int }
```

### Parallel with Dependencies

```yaml
name: parallel_workflow
steps:
  - name: fetch_data
    parallel:
      - name: users
        bash: echo "count=100"
        output: { count: int }
      - name: orders
        bash: echo "count=500"
        output: { count: int }

  - name: combine
    bash: |
      total={{ fetch_data.users.count + fetch_data.orders.count }}
      echo "total=$total"
    output: { total: int }
```

### Retry with HITL

```yaml
name: retry_workflow
steps:
  - name: attempt_operation
    bash: |
      # Simulated operation that may fail
      success=$((RANDOM % 2))
      echo "success=$success"
    repeat:
      until: "{{ attempt_operation.success }}"
      max: 3
    output: { success: bool }
    hitl: true

  - name: finalize
    if: "{{ attempt_operation.approved }}"
    bash: echo "finalized=true"
    output: { finalized: bool }
```
