"""Tests for llm_provider module."""

import os
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import patch

from llm_provider.gemini import _stream_process_output
from llm_provider.postprocessing import (
    _build_chat_agent_name,
    log_prompt_and_response,
    run_error_postprocessing,
    run_postprocessing,
    save_prompt_to_file,
)
from llm_provider.types import LLMInvocationError, LoggingContext

if TYPE_CHECKING:
    from pytest import CaptureFixture


# --- Moved tests: log_prompt_and_response ---


def test_log_prompt_and_response_basic() -> None:
    """Test basic logging of prompt and response."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="test_agent",
        )

        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)

        with open(log_file) as f:
            content = f.read()
        assert "Test prompt" in content
        assert "Test response" in content
        assert "test_agent" in content


def test_log_prompt_and_response_with_iteration() -> None:
    """Test logging with iteration number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="editor",
            iteration=5,
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "iteration 5" in content


def test_log_prompt_and_response_with_workflow_tag() -> None:
    """Test logging with workflow tag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_prompt_and_response(
            prompt="Test prompt",
            response="Test response",
            artifacts_dir=tmpdir,
            agent_type="planner",
            workflow_tag="crs",
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "tag crs" in content


def test_log_prompt_and_response_appends() -> None:
    """Test that multiple logs are appended to the same file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_prompt_and_response(
            prompt="First prompt",
            response="First response",
            artifacts_dir=tmpdir,
        )
        log_prompt_and_response(
            prompt="Second prompt",
            response="Second response",
            artifacts_dir=tmpdir,
        )

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file) as f:
            content = f.read()
        assert "First prompt" in content
        assert "Second prompt" in content
        assert "First response" in content
        assert "Second response" in content


def test_log_prompt_and_response_handles_error(
    capsys: "CaptureFixture[str]",
) -> None:
    """Test that logging errors are handled gracefully."""
    log_prompt_and_response(
        prompt="Test prompt",
        response="Test response",
        artifacts_dir="/nonexistent/path/that/cannot/exist",
    )

    captured = capsys.readouterr()
    assert "Warning" in captured.out


# --- Moved tests: _stream_process_output ---


def test_stream_process_output_basic() -> None:
    """Test basic streaming of process output."""
    process = subprocess.Popen(
        ["echo", "hello world"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = _stream_process_output(process, suppress_output=True)

    assert "hello world" in stdout
    assert stderr == ""
    assert return_code == 0


def test_stream_process_output_stderr() -> None:
    """Test streaming of process stderr."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stderr.write('error message\\n')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = _stream_process_output(process, suppress_output=True)

    assert stdout == ""
    assert "error message" in stderr
    assert return_code == 0


def test_stream_process_output_nonzero_exit() -> None:
    """Test streaming when process exits with non-zero code."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(42)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    _stdout, _stderr, return_code = _stream_process_output(
        process, suppress_output=True
    )

    assert return_code == 42


# --- New tests: types ---


def test_logging_context_defaults() -> None:
    """Test LoggingContext has sensible defaults."""
    ctx = LoggingContext()
    assert ctx.agent_type == "agent"
    assert ctx.model_size == "big"
    assert ctx.iteration is None
    assert ctx.workflow_tag is None
    assert ctx.artifacts_dir is None
    assert ctx.workflow is None
    assert ctx.timestamp is None
    assert ctx.suppress_output is False
    assert ctx.is_home_mode is False
    assert ctx.decision_counts is None


def test_logging_context_custom_values() -> None:
    """Test LoggingContext with custom values."""
    counts = {"yes": 2, "no": 1}
    ctx = LoggingContext(
        agent_type="editor",
        model_size="little",
        iteration=3,
        workflow_tag="tag1",
        artifacts_dir="/tmp/arts",
        workflow="crs",
        timestamp="240101_120000",
        suppress_output=True,
        is_home_mode=True,
        decision_counts=counts,
    )
    assert ctx.agent_type == "editor"
    assert ctx.model_size == "little"
    assert ctx.iteration == 3
    assert ctx.workflow_tag == "tag1"
    assert ctx.artifacts_dir == "/tmp/arts"
    assert ctx.workflow == "crs"
    assert ctx.timestamp == "240101_120000"
    assert ctx.suppress_output is True
    assert ctx.is_home_mode is True
    assert ctx.decision_counts == counts


def test_llm_invocation_error() -> None:
    """Test LLMInvocationError is a proper exception."""
    err = LLMInvocationError("something failed")
    assert str(err) == "something failed"
    assert isinstance(err, Exception)


# --- New tests: preprocessing ---


def test_preprocess_prompt_calls_pipeline() -> None:
    """Test that preprocess_prompt calls all 6 pipeline steps in order."""
    from llm_provider.preprocessing import preprocess_prompt

    with (
        patch(
            "llm_provider.preprocessing.process_xprompt_references",
            side_effect=lambda q: q + "[1]",
        ) as mock_xprompt,
        patch(
            "llm_provider.preprocessing.process_command_substitution",
            side_effect=lambda q: q + "[2]",
        ) as mock_cmd_sub,
        patch(
            "llm_provider.preprocessing.process_file_references",
            side_effect=lambda q, **kw: q + "[3]",
        ) as mock_file_ref,
        patch(
            "llm_provider.preprocessing.is_jinja2_template", return_value=True
        ) as mock_is_j2,
        patch(
            "llm_provider.preprocessing.render_toplevel_jinja2",
            side_effect=lambda q: q + "[4]",
        ) as mock_render_j2,
        patch(
            "llm_provider.preprocessing.format_with_prettier",
            side_effect=lambda q: q + "[5]",
        ) as mock_prettier,
        patch(
            "llm_provider.preprocessing.strip_html_comments",
            side_effect=lambda q: q + "[6]",
        ) as mock_strip,
    ):
        result = preprocess_prompt("start", is_home_mode=True)

    assert result == "start[1][2][3][4][5][6]"
    mock_xprompt.assert_called_once()
    mock_cmd_sub.assert_called_once()
    mock_file_ref.assert_called_once()
    mock_is_j2.assert_called_once()
    mock_render_j2.assert_called_once()
    mock_prettier.assert_called_once()
    mock_strip.assert_called_once()


def test_preprocess_prompt_skips_jinja_when_not_template() -> None:
    """Test that Jinja2 rendering is skipped when query is not a template."""
    from llm_provider.preprocessing import preprocess_prompt

    with (
        patch(
            "llm_provider.preprocessing.process_xprompt_references",
            side_effect=lambda q: q,
        ),
        patch(
            "llm_provider.preprocessing.process_command_substitution",
            side_effect=lambda q: q,
        ),
        patch(
            "llm_provider.preprocessing.process_file_references",
            side_effect=lambda q, **kw: q,
        ),
        patch("llm_provider.preprocessing.is_jinja2_template", return_value=False),
        patch("llm_provider.preprocessing.render_toplevel_jinja2") as mock_render_j2,
        patch(
            "llm_provider.preprocessing.format_with_prettier",
            side_effect=lambda q: q,
        ),
        patch(
            "llm_provider.preprocessing.strip_html_comments",
            side_effect=lambda q: q,
        ),
    ):
        preprocess_prompt("no jinja here")

    mock_render_j2.assert_not_called()


# --- New tests: postprocessing ---


def test_save_prompt_to_file_basic() -> None:
    """Test saving prompt to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_prompt_to_file(
            prompt="My prompt text",
            artifacts_dir=tmpdir,
            agent_type="editor",
        )

        prompt_path = os.path.join(tmpdir, "editor_prompt.md")
        assert os.path.exists(prompt_path)
        with open(prompt_path) as f:
            assert f.read() == "My prompt text"


def test_save_prompt_to_file_with_iteration() -> None:
    """Test saving prompt to file with iteration number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_prompt_to_file(
            prompt="Iter prompt",
            artifacts_dir=tmpdir,
            agent_type="planner",
            iteration=2,
        )

        prompt_path = os.path.join(tmpdir, "planner_iter_2_prompt.md")
        assert os.path.exists(prompt_path)


def test_build_chat_agent_name_same_as_workflow() -> None:
    """Test agent name is None when agent matches workflow."""
    assert _build_chat_agent_name("crs", "crs") is None


def test_build_chat_agent_name_different() -> None:
    """Test agent name is returned when different from workflow."""
    assert _build_chat_agent_name("editor", "crs") == "editor"


def test_build_chat_agent_name_same_with_error() -> None:
    """Test error suffix when agent matches workflow."""
    assert _build_chat_agent_name("crs", "crs", is_error=True) == "_ERROR"


def test_build_chat_agent_name_different_with_error() -> None:
    """Test error suffix when agent differs from workflow."""
    assert _build_chat_agent_name("editor", "crs", is_error=True) == "editor_ERROR"


def test_build_chat_agent_name_normalizes_dashes() -> None:
    """Test that dashes are normalized to underscores for comparison."""
    assert _build_chat_agent_name("my-agent", "my_agent") is None
    assert _build_chat_agent_name("my-agent", "other") == "my-agent"


def test_run_postprocessing_with_artifacts() -> None:
    """Test run_postprocessing logs to artifacts when dir is set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = LoggingContext(
            agent_type="editor",
            artifacts_dir=tmpdir,
            iteration=1,
            workflow_tag="tag",
        )
        with patch("llm_provider.postprocessing.run_bam_command") as mock_bam:
            run_postprocessing(
                query="prompt",
                response="response",
                context=ctx,
                start_timestamp="240101_120000",
            )
            mock_bam.assert_called_once()

        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)
        with open(log_file) as f:
            content = f.read()
        assert "prompt" in content
        assert "response" in content


def test_run_postprocessing_without_artifacts() -> None:
    """Test run_postprocessing works without artifacts dir."""
    ctx = LoggingContext(agent_type="editor", suppress_output=True)
    with patch("llm_provider.postprocessing.run_bam_command") as mock_bam:
        run_postprocessing(
            query="prompt",
            response="response",
            context=ctx,
            start_timestamp="240101_120000",
        )
        mock_bam.assert_not_called()


def test_run_postprocessing_audio_suppressed() -> None:
    """Test run_postprocessing doesn't play audio when suppressed."""
    ctx = LoggingContext(suppress_output=True)
    with patch("llm_provider.postprocessing.run_bam_command") as mock_bam:
        run_postprocessing(
            query="q",
            response="r",
            context=ctx,
            start_timestamp="240101_120000",
        )
        mock_bam.assert_not_called()


def test_run_error_postprocessing() -> None:
    """Test run_error_postprocessing displays error and logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = LoggingContext(
            agent_type="editor",
            artifacts_dir=tmpdir,
            workflow="crs",
        )
        with (
            patch(
                "llm_provider.postprocessing.print_prompt_and_response"
            ) as mock_print,
            patch("llm_provider.postprocessing.save_chat_history") as mock_save,
        ):
            run_error_postprocessing(
                query="prompt",
                error_content="bad error",
                context=ctx,
                agent_type_with_size="editor [BIG]",
                start_timestamp="240101_120000",
            )

            mock_print.assert_called_once()
            assert "ERROR" in mock_print.call_args[1]["agent_type"]
            mock_save.assert_called_once()

        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)
        with open(log_file) as f:
            content = f.read()
        assert "bad error" in content
        assert "editor_ERROR" in content


# --- New tests: gemini provider ---


def test_gemini_provider_name() -> None:
    """Test GeminiProvider.name returns 'gemini'."""
    from llm_provider.gemini import GeminiProvider

    provider = GeminiProvider()
    assert provider.name == "gemini"
