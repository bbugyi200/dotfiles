"""Tests for the WorkflowExecutor class."""

import tempfile
from unittest.mock import MagicMock, patch

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


class TestWorkflowExecutorValidation:
    """Tests for output validation in WorkflowExecutor."""

    def test_validation_error_raises_without_hitl(self) -> None:
        """Test that validation errors raise WorkflowExecutionError without HITL."""
        mock_output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"field1": {"type": "string"}},
                "required": ["field1"],
            },
        )
        step = WorkflowStep(
            name="test_step",
            prompt="#json_output\nGenerate output",
            output=mock_output_spec,
            hitl=False,
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_handler=None,
            )

            # Mock agent response with invalid output (missing required field)
            invalid_response = "Sorry, I couldn't generate the output."

            with (
                patch("gemini_wrapper.invoke_agent") as mock_invoke,
                patch("xprompt.get_primary_output_schema") as mock_schema,
                patch(
                    "xprompt.process_xprompt_references",
                    return_value="expanded prompt",
                ),
            ):
                mock_invoke.return_value = MagicMock(content=invalid_response)
                mock_schema.return_value = mock_output_spec

                with pytest.raises(WorkflowExecutionError) as exc_info:
                    executor.execute()

                assert "output validation failed" in str(exc_info.value)

    def test_validation_error_includes_error_in_hitl_output(self) -> None:
        """Test that validation errors are included in output when HITL is enabled."""
        mock_output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"field1": {"type": "string"}},
                "required": ["field1"],
            },
        )
        step = WorkflowStep(
            name="test_step",
            prompt="#json_output\nGenerate output",
            output=mock_output_spec,
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

            # Response with valid JSON but wrong schema (missing required field)
            response_with_wrong_schema = '{"wrong_field": "value"}'

            with (
                patch("gemini_wrapper.invoke_agent") as mock_invoke,
                patch("xprompt.get_primary_output_schema") as mock_schema,
                patch(
                    "xprompt.process_xprompt_references",
                    return_value="expanded prompt",
                ),
            ):
                mock_invoke.return_value = MagicMock(content=response_with_wrong_schema)
                mock_schema.return_value = mock_output_spec

                result = executor.execute()

                # HITL handler should have been called
                assert mock_handler.prompt.called  # type: ignore[attr-defined]
                call_args = mock_handler.prompt.call_args  # type: ignore[attr-defined]
                output = call_args[0][2]  # Third positional arg is output

                # Output should contain validation error
                assert "_validation_error" in output
                assert result is True  # Workflow should complete since HITL accepted

    def test_parse_error_raises_without_hitl(self) -> None:
        """Test that JSON/YAML parse errors raise WorkflowExecutionError without HITL."""
        mock_output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"field1": {"type": "string"}},
                "required": ["field1"],
            },
        )
        step = WorkflowStep(
            name="test_step",
            prompt="#json_output\nGenerate output",
            output=mock_output_spec,
            hitl=False,
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_handler=None,
            )

            # Response with no valid JSON/YAML at all
            unparseable_response = "This is just plain text with no JSON or YAML."

            with (
                patch("gemini_wrapper.invoke_agent") as mock_invoke,
                patch("xprompt.get_primary_output_schema") as mock_schema,
                patch(
                    "xprompt.process_xprompt_references",
                    return_value="expanded prompt",
                ),
            ):
                mock_invoke.return_value = MagicMock(content=unparseable_response)
                mock_schema.return_value = mock_output_spec

                with pytest.raises(WorkflowExecutionError) as exc_info:
                    executor.execute()

                assert "output validation failed" in str(exc_info.value)
                assert "Could not extract valid JSON or YAML" in str(exc_info.value)

    def test_valid_output_passes_validation(self) -> None:
        """Test that valid output passes validation without errors."""
        mock_output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"field1": {"type": "string"}},
                "required": ["field1"],
            },
        )
        step = WorkflowStep(
            name="test_step",
            prompt="#json_output\nGenerate output",
            output=mock_output_spec,
            hitl=False,
        )
        workflow = _create_test_workflow(steps=[step])

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                workflow=workflow,
                args={},
                artifacts_dir=tmpdir,
                hitl_handler=None,
            )

            # Valid response matching schema
            valid_response = '{"field1": "valid value"}'

            with (
                patch("gemini_wrapper.invoke_agent") as mock_invoke,
                patch("xprompt.get_primary_output_schema") as mock_schema,
                patch(
                    "xprompt.process_xprompt_references",
                    return_value="expanded prompt",
                ),
            ):
                mock_invoke.return_value = MagicMock(content=valid_response)
                mock_schema.return_value = mock_output_spec

                result = executor.execute()

                assert result is True
                assert executor.context["test_step"]["field1"] == "valid value"
                assert "_validation_error" not in executor.context["test_step"]

    def test_hitl_reject_stops_workflow_on_validation_error(self) -> None:
        """Test that rejecting in HITL mode stops the workflow."""
        mock_output_spec = OutputSpec(
            type="json_schema",
            schema={
                "type": "object",
                "properties": {"field1": {"type": "string"}},
                "required": ["field1"],
            },
        )
        step = WorkflowStep(
            name="test_step",
            prompt="#json_output\nGenerate output",
            output=mock_output_spec,
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

            # Response with wrong schema
            response_with_wrong_schema = '{"wrong_field": "value"}'

            with (
                patch("gemini_wrapper.invoke_agent") as mock_invoke,
                patch("xprompt.get_primary_output_schema") as mock_schema,
                patch(
                    "xprompt.process_xprompt_references",
                    return_value="expanded prompt",
                ),
            ):
                mock_invoke.return_value = MagicMock(content=response_with_wrong_schema)
                mock_schema.return_value = mock_output_spec

                result = executor.execute()

                # Workflow should fail because user rejected
                assert result is False


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
