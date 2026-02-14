"""Tests for the WorkflowExecutor class."""

import tempfile
from unittest.mock import MagicMock

import pytest
from xprompt import HITLHandler, HITLResult, WorkflowExecutor
from xprompt.models import OutputSpec
from xprompt.workflow_executor_utils import parse_bash_output
from xprompt.workflow_models import Workflow, WorkflowExecutionError, WorkflowStep


def _create_test_workflow(
    name: str = "test_workflow",
    steps: list[WorkflowStep] | None = None,
) -> Workflow:
    """Create a test workflow with the given steps."""
    if steps is None:
        steps = [
            WorkflowStep(
                name="step1",
                prompt="Test prompt",
                output=OutputSpec(
                    type="json_schema",
                    schema={
                        "type": "object",
                        "properties": {"result": {"type": "string"}},
                        "required": ["result"],
                    },
                ),
                hitl=False,
            )
        ]
    return Workflow(
        name=name,
        steps=steps,
    )


def _create_mock_hitl_handler(action: str = "accept") -> HITLHandler:
    """Create a mock HITL handler that returns the specified action."""
    handler = MagicMock(spec=HITLHandler)
    handler.prompt.return_value = HITLResult(action=action)
    return handler


class TestShouldHitl:
    """Tests for the _should_hitl method on WorkflowExecutor."""

    def test_should_hitl_no_override_respects_step(self) -> None:
        """Test _should_hitl returns step.hitl when no override set."""
        step_hitl = WorkflowStep(name="s1", bash="echo ok", hitl=True)
        step_no_hitl = WorkflowStep(name="s2", bash="echo ok", hitl=False)
        workflow = _create_test_workflow(steps=[step_hitl, step_no_hitl])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow, args={}, artifacts_dir=tmpdir
            )
            assert executor._should_hitl(step_hitl) is True
            assert executor._should_hitl(step_no_hitl) is False

    def test_should_hitl_override_true_forces_hitl(self) -> None:
        """Test _should_hitl returns True when override is True."""
        step = WorkflowStep(name="s1", bash="echo ok", hitl=False)
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_override=True,
            )
            assert executor._should_hitl(step) is True

    def test_should_hitl_override_false_skips_hitl(self) -> None:
        """Test _should_hitl returns False when override is False."""
        step = WorkflowStep(name="s1", bash="echo ok", hitl=True)
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_override=False,
            )
            assert executor._should_hitl(step) is False


class TestPythonStepExecution:
    """Tests for Python step execution."""

    def test_python_step_key_value_output(self) -> None:
        """Test Python step with key=value output format."""
        step = WorkflowStep(
            name="python_step",
            python='print("key1=value1")\nprint("key2=value2")',
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            result = executor.execute()

            assert result is True
            assert executor.context["python_step"]["key1"] == "value1"
            assert executor.context["python_step"]["key2"] == "value2"

    def test_python_step_json_output(self) -> None:
        """Test Python step with JSON output format."""
        step = WorkflowStep(
            name="python_step",
            python='import json; print(json.dumps({"name": "test", "count": 42}))',
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            result = executor.execute()

            assert result is True
            assert executor.context["python_step"]["name"] == "test"
            assert executor.context["python_step"]["count"] == 42

    def test_python_step_with_jinja_context(self) -> None:
        """Test Python step can access Jinja2 context variables."""
        step = WorkflowStep(
            name="python_step",
            python='print("result={{ input_value }}_processed")',
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={"input_value": "hello"},
                artifacts_dir=tmpdir,
            )

            result = executor.execute()

            assert result is True
            assert executor.context["python_step"]["result"] == "hello_processed"

    def test_python_step_validation_error(self) -> None:
        """Test Python step raises error when validation fails."""
        step = WorkflowStep(
            name="python_step",
            python='print("wrong_key=value")',
            output=OutputSpec(
                type="json_schema",
                schema={
                    "type": "object",
                    "properties": {"required_key": {"type": "string"}},
                    "required": ["required_key"],
                },
            ),
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            with pytest.raises(WorkflowExecutionError) as exc_info:
                executor.execute()

            assert "output validation failed" in str(exc_info.value)

    def test_python_step_nonzero_exit_raises_error(self) -> None:
        """Test Python step raises error on non-zero exit code."""
        step = WorkflowStep(
            name="python_step",
            python='import sys; print("error=something failed", file=sys.stderr); sys.exit(1)',
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            with pytest.raises(WorkflowExecutionError) as exc_info:
                executor.execute()

            assert "Python step 'python_step' failed" in str(exc_info.value)

    def test_python_step_with_hitl_accept(self) -> None:
        """Test Python step with HITL that accepts."""
        step = WorkflowStep(
            name="python_step",
            python='print("status=ready")',
            hitl=True,
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_handler = _create_mock_hitl_handler(action="accept")

            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_handler=mock_handler,
            )

            result = executor.execute()

            assert result is True
            assert mock_handler.prompt.called  # type: ignore[attr-defined]
            # Check that HITL was called with "python" step type
            call_args = mock_handler.prompt.call_args  # type: ignore[attr-defined]
            assert call_args[0][1] == "python"
            # Output should have approved flag set
            assert executor.context["python_step"]["approved"] is True
            # Workflow status should be completed, not stuck on waiting_hitl
            assert executor.state.status == "completed"

    def test_python_step_with_hitl_reject(self) -> None:
        """Test Python step with HITL that rejects."""
        step = WorkflowStep(
            name="python_step",
            python='print("status=ready")',
            hitl=True,
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_handler = _create_mock_hitl_handler(action="reject")

            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_handler=mock_handler,
            )

            result = executor.execute()

            assert result is False


class TestParseBashOutput:
    """Tests for parse_bash_output function."""

    def test_parse_json_object(self) -> None:
        """Test parsing JSON object output."""
        output = '{"key": "value", "num": 123}'
        result = parse_bash_output(output)
        assert result == {"key": "value", "num": 123}

    def test_parse_json_array(self) -> None:
        """Test parsing JSON array output."""
        output = "[1, 2, 3]"
        result = parse_bash_output(output)
        assert result == [1, 2, 3]

    def test_parse_key_value(self) -> None:
        """Test parsing key=value output."""
        output = "key1=value1\nkey2=value2"
        result = parse_bash_output(output)
        assert result == {"key1": "value1", "key2": "value2"}

    def test_parse_plain_text(self) -> None:
        """Test parsing plain text output."""
        output = "Just some plain text"
        result = parse_bash_output(output)
        assert result == {"_output": "Just some plain text"}


class TestEmbeddedWorkflowExpansion:
    """Tests for embedded workflow expansion in prompts."""

    def test_embedded_workflow_dashes_inline_gets_newlines(self) -> None:
        """Test that --- marker gets stripped and \\n\\n prepended when not at line start."""
        from unittest.mock import patch

        # Create a workflow with prompt_part starting with ---
        workflow_with_dashes = Workflow(
            name="inject_workflow",
            steps=[
                WorkflowStep(
                    name="inject",
                    prompt_part="---\nIMPORTANT: Additional instructions",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple workflow to get an executor
            main_workflow = _create_test_workflow()
            executor = WorkflowExecutor(
                workflow=main_workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            # Mock get_all_workflows at the loader module where it's imported from
            with patch("xprompt.loader.get_all_workflows") as mock_get_workflows:
                mock_get_workflows.return_value = {
                    "inject_workflow": workflow_with_dashes
                }

                # Test case: workflow ref inline (not at line start)
                prompt = "Do NOT modify any files. #inject_workflow"
                expanded, _, _ = executor._expand_embedded_workflows_in_prompt(prompt)

                # The --- marker is stripped but \n\n is still prepended
                assert expanded == (
                    "Do NOT modify any files. \n\nIMPORTANT: Additional instructions"
                )

    def test_embedded_workflow_dashes_at_line_start_no_extra_newlines(self) -> None:
        """Test that --- marker at line start is stripped without extra newlines."""
        from unittest.mock import patch

        workflow_with_dashes = Workflow(
            name="inject_workflow",
            steps=[
                WorkflowStep(
                    name="inject",
                    prompt_part="---\nIMPORTANT: Additional instructions",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            main_workflow = _create_test_workflow()
            executor = WorkflowExecutor(
                workflow=main_workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            with patch("xprompt.loader.get_all_workflows") as mock_get_workflows:
                mock_get_workflows.return_value = {
                    "inject_workflow": workflow_with_dashes
                }

                # Test case: workflow ref at start of line
                prompt = "Some text.\n#inject_workflow"
                expanded, _, _ = executor._expand_embedded_workflows_in_prompt(prompt)

                # The --- marker is stripped, content directly follows the newline
                assert expanded == ("Some text.\nIMPORTANT: Additional instructions")

    def test_embedded_workflow_hashes_inline_gets_newlines(self) -> None:
        """Test that ### content gets \\n\\n prepended when not at line start."""
        from unittest.mock import patch

        workflow_with_hashes = Workflow(
            name="inject_workflow",
            steps=[
                WorkflowStep(
                    name="inject",
                    prompt_part="### Section Header\nSection content",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            main_workflow = _create_test_workflow()
            executor = WorkflowExecutor(
                workflow=main_workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            with patch("xprompt.loader.get_all_workflows") as mock_get_workflows:
                mock_get_workflows.return_value = {
                    "inject_workflow": workflow_with_hashes
                }

                # Test case: workflow ref inline (not at line start)
                prompt = "Context text. #inject_workflow"
                expanded, _, _ = executor._expand_embedded_workflows_in_prompt(prompt)

                # Should prepend \n\n before the ### content
                assert "\n\n### Section Header" in expanded


class TestOutputTypesPreservation:
    """Tests for output_types preservation in _save_prompt_step_marker."""

    def test_output_types_preserved_when_not_provided(self) -> None:
        """Test that output_types from existing marker is preserved when caller doesn't pass it."""
        import json
        import os

        step = WorkflowStep(
            name="step1",
            prompt="Test",
            output=OutputSpec(
                type="json_schema",
                schema={
                    "type": "object",
                    "properties": {
                        "diff_file": {"type": "path"},
                        "summary": {"type": "text"},
                    },
                },
            ),
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            from xprompt.workflow_models import StepState, StepStatus

            step_state = StepState(name="step1", status=StepStatus.IN_PROGRESS)

            # First save: includes output_types
            executor._save_prompt_step_marker(
                "step1",
                step_state,
                "prompt",
                step_index=0,
                output_types={"diff_file": "path", "summary": "text"},
            )

            marker_path = os.path.join(tmpdir, "prompt_step_step1.json")
            with open(marker_path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["output_types"] == {"diff_file": "path", "summary": "text"}

            # Second save: does NOT pass output_types (simulates _execute_prompt_step)
            step_state.status = StepStatus.COMPLETED
            executor._save_prompt_step_marker(
                "step1",
                step_state,
                "prompt",
            )

            with open(marker_path, encoding="utf-8") as f:
                data = json.load(f)
            # output_types should be preserved from the first save
            assert data["output_types"] == {"diff_file": "path", "summary": "text"}

    def test_output_types_overwritten_when_explicitly_provided(self) -> None:
        """Test that explicitly provided output_types overwrites existing."""
        import json
        import os

        step = WorkflowStep(name="step1", prompt="Test")
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
            )

            from xprompt.workflow_models import StepState, StepStatus

            step_state = StepState(name="step1", status=StepStatus.IN_PROGRESS)

            # First save with output_types
            executor._save_prompt_step_marker(
                "step1",
                step_state,
                "prompt",
                output_types={"old_field": "text"},
            )

            # Second save with different output_types
            executor._save_prompt_step_marker(
                "step1",
                step_state,
                "prompt",
                output_types={"new_field": "path"},
            )

            marker_path = os.path.join(tmpdir, "prompt_step_step1.json")
            with open(marker_path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["output_types"] == {"new_field": "path"}


class TestSubstepSuffix:
    """Tests for the get_substep_suffix helper function."""

    def test_substep_suffix_first_letters(self) -> None:
        """Test that indices 0-25 map to a-z."""
        from xprompt.workflow_output import get_substep_suffix

        assert get_substep_suffix(0) == "a"
        assert get_substep_suffix(1) == "b"
        assert get_substep_suffix(25) == "z"

    def test_substep_suffix_double_letters(self) -> None:
        """Test that indices 26+ map to aa, ab, etc."""
        from xprompt.workflow_output import get_substep_suffix

        assert get_substep_suffix(26) == "aa"
        assert get_substep_suffix(27) == "ab"
        assert get_substep_suffix(51) == "az"
        assert get_substep_suffix(52) == "ba"


class TestParentStepContext:
    """Tests for parent step context in embedded workflow output."""

    def test_on_step_start_with_parent_context(self) -> None:
        """Test that on_step_start formats embedded steps correctly."""
        from io import StringIO

        from rich.console import Console
        from xprompt.workflow_output import (
            ParentStepContext,
            WorkflowOutputHandler,
        )

        # Create a console that writes to a string buffer (no_color to avoid ANSI)
        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True, width=100)
        handler = WorkflowOutputHandler(console=console)

        # Create parent step context (parent step 1 of 7 total)
        parent_ctx = ParentStepContext(step_index=0, total_steps=7)

        # Call on_step_start with parent context (substep 0)
        handler.on_step_start(
            step_name="check_changes",
            step_type="bash",
            step_index=0,
            total_steps=4,
            parent_step_context=parent_ctx,
        )

        # Check output contains the expected format "1a/7"
        result = output.getvalue()
        assert "Step 1a/7: check_changes (bash)" in result

    def test_on_step_start_without_parent_context(self) -> None:
        """Test that on_step_start uses regular numbering without parent context."""
        from io import StringIO

        from rich.console import Console
        from xprompt.workflow_output import WorkflowOutputHandler

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True, width=100)
        handler = WorkflowOutputHandler(console=console)

        # Call on_step_start without parent context
        handler.on_step_start(
            step_name="test_step",
            step_type="prompt",
            step_index=2,
            total_steps=5,
        )

        # Check output contains the expected format "3/5" (0-indexed + 1)
        result = output.getvalue()
        assert "Step 3/5: test_step (prompt)" in result

    def test_on_step_start_multiple_substeps(self) -> None:
        """Test formatting of multiple embedded substeps."""
        from io import StringIO

        from rich.console import Console
        from xprompt.workflow_output import (
            ParentStepContext,
            WorkflowOutputHandler,
        )

        output = StringIO()
        console = Console(file=output, force_terminal=False, no_color=True, width=100)
        handler = WorkflowOutputHandler(console=console)

        parent_ctx = ParentStepContext(step_index=2, total_steps=10)

        # Substeps 0, 1, 2 should produce 3a, 3b, 3c
        for i in range(3):
            handler.on_step_start(
                step_name=f"substep_{i}",
                step_type="bash",
                step_index=i,
                total_steps=3,
                parent_step_context=parent_ctx,
            )

        result = output.getvalue()
        assert "Step 3a/10:" in result
        assert "Step 3b/10:" in result
        assert "Step 3c/10:" in result
