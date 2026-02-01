"""Tests for the WorkflowExecutor class."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest
from xprompt import HITLHandler, HITLResult, WorkflowExecutor
from xprompt.models import OutputSpec
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
                agent="test_agent",
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
            agent="test_agent",
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
            agent="test_agent",
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
            agent="test_agent",
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
            agent="test_agent",
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
            agent="test_agent",
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
