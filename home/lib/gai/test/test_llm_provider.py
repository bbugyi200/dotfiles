"""Tests for the llm_provider abstraction layer."""

import os
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from llm_provider._invoke import invoke_agent
from llm_provider._subprocess import stream_process_output
from llm_provider.base import LLMProvider
from llm_provider.claude import ClaudeCodeProvider
from llm_provider.gemini import GeminiProvider
from llm_provider.postprocessing import log_prompt_and_response, save_prompt_to_file
from llm_provider.registry import _REGISTRY, get_provider, register_provider
from llm_provider.types import _MODEL_SIZE_TO_TIER, LoggingContext, ModelTier

if TYPE_CHECKING:
    from pytest import CaptureFixture


# --- types.py tests ---


def test_model_size_to_tier_mapping() -> None:
    """Test the model_size to model_tier mapping."""
    assert _MODEL_SIZE_TO_TIER["big"] == "large"
    assert _MODEL_SIZE_TO_TIER["little"] == "small"


def test_model_tier_type() -> None:
    """Test ModelTier type accepts valid values."""
    tier_large: ModelTier = "large"
    tier_small: ModelTier = "small"
    assert tier_large == "large"
    assert tier_small == "small"


def test_logging_context_defaults() -> None:
    """Test LoggingContext dataclass default values."""
    ctx = LoggingContext()
    assert ctx.agent_type == "agent"
    assert ctx.iteration is None
    assert ctx.workflow_tag is None
    assert ctx.artifacts_dir is None
    assert ctx.suppress_output is False
    assert ctx.workflow is None
    assert ctx.timestamp is None
    assert ctx.is_home_mode is False
    assert ctx.decision_counts is None


def test_logging_context_custom_values() -> None:
    """Test LoggingContext dataclass with custom values."""
    ctx = LoggingContext(
        agent_type="editor",
        iteration=3,
        workflow_tag="test-tag",
        artifacts_dir="/tmp/test",
        suppress_output=True,
        workflow="crs",
        timestamp="260214_120000",
        is_home_mode=True,
        decision_counts={"yes": 5, "no": 2},
    )
    assert ctx.agent_type == "editor"
    assert ctx.iteration == 3
    assert ctx.workflow_tag == "test-tag"
    assert ctx.artifacts_dir == "/tmp/test"
    assert ctx.suppress_output is True
    assert ctx.workflow == "crs"
    assert ctx.timestamp == "260214_120000"
    assert ctx.is_home_mode is True
    assert ctx.decision_counts == {"yes": 5, "no": 2}


# --- base.py tests ---


def test_llm_provider_is_abstract() -> None:
    """Test that LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_llm_provider_subclass() -> None:
    """Test that a concrete subclass can be created."""

    class MockProvider(LLMProvider):
        def invoke(
            self,
            prompt: str,
            *,
            model_tier: ModelTier,
            suppress_output: bool = False,
        ) -> str:
            return f"mock response to: {prompt}"

    provider = MockProvider()
    result = provider.invoke("hello", model_tier="large")
    assert result == "mock response to: hello"


# --- registry.py tests ---


def test_register_and_get_provider() -> None:
    """Test registering and retrieving a provider."""

    class TestProvider(LLMProvider):
        def invoke(
            self,
            prompt: str,
            *,
            model_tier: ModelTier,
            suppress_output: bool = False,
        ) -> str:
            return "test"

    register_provider("test_provider", TestProvider)
    try:
        provider = get_provider("test_provider")
        assert isinstance(provider, TestProvider)
    finally:
        # Clean up
        _REGISTRY.pop("test_provider", None)


def test_get_provider_unknown_raises() -> None:
    """Test that requesting an unknown provider raises KeyError."""
    with pytest.raises(KeyError, match="Unknown LLM provider"):
        get_provider("nonexistent_provider_xyz")


def test_gemini_provider_registered_by_default() -> None:
    """Test that GeminiProvider is registered as 'gemini' by default."""
    provider = get_provider("gemini")
    assert isinstance(provider, GeminiProvider)


def test_get_default_provider_returns_gemini() -> None:
    """Test that the default provider is 'gemini'."""
    provider = get_provider()
    assert isinstance(provider, GeminiProvider)


# --- postprocessing.py tests ---


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


def test_save_prompt_to_file_basic() -> None:
    """Test saving a prompt to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_prompt_to_file(
            prompt="My test prompt",
            artifacts_dir=tmpdir,
            agent_type="test_agent",
        )

        prompt_file = os.path.join(tmpdir, "test_agent_prompt.md")
        assert os.path.exists(prompt_file)
        with open(prompt_file) as f:
            assert f.read() == "My test prompt"


def test_save_prompt_to_file_with_iteration() -> None:
    """Test saving a prompt with iteration number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_prompt_to_file(
            prompt="Iteration prompt",
            artifacts_dir=tmpdir,
            agent_type="editor",
            iteration=3,
        )

        prompt_file = os.path.join(tmpdir, "editor_iter_3_prompt.md")
        assert os.path.exists(prompt_file)


# --- gemini.py tests ---


def test_stream_process_output_basic() -> None:
    """Test basic streaming of process output."""
    process = subprocess.Popen(
        ["echo", "hello world"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr, return_code = stream_process_output(process, suppress_output=True)

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

    stdout, stderr, return_code = stream_process_output(process, suppress_output=True)

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

    stdout, stderr, return_code = stream_process_output(process, suppress_output=True)

    assert return_code == 42


def test_gemini_provider_is_llm_provider() -> None:
    """Test that GeminiProvider is a proper LLMProvider subclass."""
    provider = GeminiProvider()
    assert isinstance(provider, LLMProvider)


# --- _invoke.py tests ---


@patch("llm_provider._invoke.get_provider")
@patch("llm_provider._invoke.preprocess_prompt")
@patch("llm_provider._invoke.print_prompt_and_response")
@patch("llm_provider._invoke.print_decision_counts")
@patch("llm_provider._invoke.postprocess_success")
def test_invoke_agent_with_mocked_provider(
    mock_postprocess: MagicMock,
    mock_print_counts: MagicMock,
    mock_print_prompt: MagicMock,
    mock_preprocess: MagicMock,
    mock_get_provider: MagicMock,
) -> None:
    """Test invoke_agent with a mocked provider."""
    # Set up mocks
    mock_preprocess.return_value = "preprocessed prompt"
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = "mock response"
    mock_get_provider.return_value = mock_provider

    # Call invoke_agent
    result = invoke_agent(
        "raw prompt",
        agent_type="test",
        model_tier="large",
        suppress_output=True,
    )

    # Verify preprocessing was called
    mock_preprocess.assert_called_once_with("raw prompt", is_home_mode=False)

    # Verify provider was called
    mock_provider.invoke.assert_called_once_with(
        "preprocessed prompt",
        model_tier="large",
        suppress_output=True,
    )

    # Verify result
    assert result.content == "mock response"


@patch("llm_provider._invoke.get_provider")
@patch("llm_provider._invoke.preprocess_prompt")
@patch("llm_provider._invoke.postprocess_error")
def test_invoke_agent_handles_error(
    mock_postprocess_error: MagicMock,
    mock_preprocess: MagicMock,
    mock_get_provider: MagicMock,
) -> None:
    """Test invoke_agent handles provider errors gracefully."""
    mock_preprocess.return_value = "preprocessed prompt"
    mock_provider = MagicMock()
    mock_provider.invoke.side_effect = Exception("test error")
    mock_get_provider.return_value = mock_provider

    result = invoke_agent(
        "raw prompt",
        agent_type="test",
        suppress_output=True,
    )

    assert "Error: test error" in result.content
    mock_postprocess_error.assert_called_once()


@patch("llm_provider._invoke.get_provider")
@patch("llm_provider._invoke.preprocess_prompt")
@patch("llm_provider._invoke.print_prompt_and_response")
@patch("llm_provider._invoke.postprocess_success")
def test_invoke_agent_model_size_backward_compat(
    mock_postprocess: MagicMock,
    mock_print_prompt: MagicMock,
    mock_preprocess: MagicMock,
    mock_get_provider: MagicMock,
) -> None:
    """Test invoke_agent with deprecated model_size parameter."""
    mock_preprocess.return_value = "preprocessed"
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = "response"
    mock_get_provider.return_value = mock_provider

    invoke_agent(
        "prompt",
        agent_type="test",
        model_size="little",
        suppress_output=True,
    )

    # Should have converted "little" to "small"
    mock_provider.invoke.assert_called_once_with(
        "preprocessed",
        model_tier="small",
        suppress_output=True,
    )


@patch("llm_provider._invoke.get_provider")
@patch("llm_provider._invoke.preprocess_prompt")
@patch("llm_provider._invoke.postprocess_success")
def test_invoke_agent_model_tier_override_env(
    mock_postprocess: MagicMock,
    mock_preprocess: MagicMock,
    mock_get_provider: MagicMock,
) -> None:
    """Test that GAI_MODEL_TIER_OVERRIDE env var overrides model_tier."""
    mock_preprocess.return_value = "preprocessed"
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = "response"
    mock_get_provider.return_value = mock_provider

    os.environ["GAI_MODEL_TIER_OVERRIDE"] = "small"
    try:
        invoke_agent(
            "prompt",
            agent_type="test",
            model_tier="large",  # Should be overridden to "small"
            suppress_output=True,
        )

        mock_provider.invoke.assert_called_once_with(
            "preprocessed",
            model_tier="small",
            suppress_output=True,
        )
    finally:
        del os.environ["GAI_MODEL_TIER_OVERRIDE"]


@patch("llm_provider._invoke.get_provider")
@patch("llm_provider._invoke.preprocess_prompt")
@patch("llm_provider._invoke.postprocess_success")
def test_invoke_agent_model_size_override_env_compat(
    mock_postprocess: MagicMock,
    mock_preprocess: MagicMock,
    mock_get_provider: MagicMock,
) -> None:
    """Test that GAI_MODEL_SIZE_OVERRIDE env var still works."""
    mock_preprocess.return_value = "preprocessed"
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = "response"
    mock_get_provider.return_value = mock_provider

    os.environ["GAI_MODEL_SIZE_OVERRIDE"] = "little"
    try:
        invoke_agent(
            "prompt",
            agent_type="test",
            model_tier="large",  # Should be overridden to "small" via "little"
            suppress_output=True,
        )

        mock_provider.invoke.assert_called_once_with(
            "preprocessed",
            model_tier="small",
            suppress_output=True,
        )
    finally:
        del os.environ["GAI_MODEL_SIZE_OVERRIDE"]


# --- Backward compatibility tests ---


def test_gemini_wrapper_invoke_agent_still_importable() -> None:
    """Test that invoke_agent can still be imported from gemini_wrapper."""
    from gemini_wrapper import invoke_agent as gw_invoke_agent

    assert callable(gw_invoke_agent)


def test_gemini_wrapper_command_wrapper_still_importable() -> None:
    """Test that GeminiCommandWrapper can still be imported from gemini_wrapper."""
    from gemini_wrapper import GeminiCommandWrapper

    wrapper = GeminiCommandWrapper()
    assert wrapper.model_size == "big"
    assert wrapper.agent_type == "agent"


def test_gemini_wrapper_log_prompt_still_importable() -> None:
    """Test that _log_prompt_and_response is still importable from wrapper."""
    from gemini_wrapper.wrapper import _log_prompt_and_response as log_fn

    assert callable(log_fn)


def test_gemini_wrapper_stream_output_still_importable() -> None:
    """Test that _stream_process_output is still importable from wrapper."""
    from gemini_wrapper.wrapper import _stream_process_output as stream_fn

    assert callable(stream_fn)


def test_llm_provider_invoke_agent_importable() -> None:
    """Test that invoke_agent can be imported from llm_provider."""
    from llm_provider import invoke_agent as llm_invoke_agent

    assert callable(llm_invoke_agent)


# --- claude.py tests ---


def test_claude_provider_is_llm_provider() -> None:
    """Test that ClaudeCodeProvider is a proper LLMProvider subclass."""
    provider = ClaudeCodeProvider()
    assert isinstance(provider, LLMProvider)


def test_claude_provider_registered() -> None:
    """Test that ClaudeCodeProvider is registered as 'claude'."""
    provider = get_provider("claude")
    assert isinstance(provider, ClaudeCodeProvider)


@patch("llm_provider.claude.stream_process_output")
@patch("llm_provider.claude.subprocess.Popen")
@patch("llm_provider.claude.gemini_timer")
def test_claude_provider_builds_correct_command_large(
    mock_timer: MagicMock,
    mock_popen: MagicMock,
    mock_stream: MagicMock,
) -> None:
    """Test that ClaudeCodeProvider builds the correct command for large tier."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    mock_stream.return_value = ("response text", "", 0)

    provider = ClaudeCodeProvider()
    result = provider.invoke("test prompt", model_tier="large", suppress_output=True)

    # Verify Popen was called with correct args
    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "opus"
    assert "--output-format" in cmd
    fmt_idx = cmd.index("--output-format")
    assert cmd[fmt_idx + 1] == "text"
    assert "--dangerously-skip-permissions" in cmd

    assert result == "response text"


@patch("llm_provider.claude.stream_process_output")
@patch("llm_provider.claude.subprocess.Popen")
@patch("llm_provider.claude.gemini_timer")
def test_claude_provider_builds_correct_command_small(
    mock_timer: MagicMock,
    mock_popen: MagicMock,
    mock_stream: MagicMock,
) -> None:
    """Test that ClaudeCodeProvider uses sonnet for small tier."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    mock_stream.return_value = ("response text", "", 0)

    provider = ClaudeCodeProvider()
    provider.invoke("test prompt", model_tier="small", suppress_output=True)

    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "sonnet"


@patch.dict(os.environ, {"GAI_CLAUDE_LARGE_ARGS": "--verbose --debug"})
@patch("llm_provider.claude.stream_process_output")
@patch("llm_provider.claude.subprocess.Popen")
@patch("llm_provider.claude.gemini_timer")
def test_claude_provider_extra_args_from_env_large(
    mock_timer: MagicMock,
    mock_popen: MagicMock,
    mock_stream: MagicMock,
) -> None:
    """Test that GAI_CLAUDE_LARGE_ARGS env var is parsed into command."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    mock_stream.return_value = ("response", "", 0)

    provider = ClaudeCodeProvider()
    provider.invoke("test", model_tier="large", suppress_output=True)

    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert "--verbose" in cmd
    assert "--debug" in cmd


@patch.dict(os.environ, {"GAI_CLAUDE_SMALL_ARGS": "--max-tokens 1000"})
@patch("llm_provider.claude.stream_process_output")
@patch("llm_provider.claude.subprocess.Popen")
@patch("llm_provider.claude.gemini_timer")
def test_claude_provider_extra_args_from_env_small(
    mock_timer: MagicMock,
    mock_popen: MagicMock,
    mock_stream: MagicMock,
) -> None:
    """Test that GAI_CLAUDE_SMALL_ARGS env var is parsed into command."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    mock_stream.return_value = ("response", "", 0)

    provider = ClaudeCodeProvider()
    provider.invoke("test", model_tier="small", suppress_output=True)

    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert "--max-tokens" in cmd
    assert "1000" in cmd


@patch("llm_provider.claude.stream_process_output")
@patch("llm_provider.claude.subprocess.Popen")
@patch("llm_provider.claude.gemini_timer")
def test_claude_provider_raises_on_failure(
    mock_timer: MagicMock,
    mock_popen: MagicMock,
    mock_stream: MagicMock,
) -> None:
    """Test that ClaudeCodeProvider raises CalledProcessError on non-zero exit."""
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    mock_stream.return_value = ("", "some error", 1)

    provider = ClaudeCodeProvider()
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        provider.invoke("test", model_tier="large", suppress_output=True)

    assert exc_info.value.returncode == 1
    assert exc_info.value.stderr == "some error"
