"""Tests for handle_reword and its helpers in the reword module."""

import os
from unittest.mock import MagicMock, patch

from ace.handlers.reword import (
    _add_prettier_ignore_before_tags,
    _fetch_cl_description,
    _open_editor_with_content,
    _strip_prettier_ignore,
    handle_reword,
)

# === Tests for _add_prettier_ignore_before_tags ===


def test_add_prettier_ignore_inserts_before_tag_block() -> None:
    """Test that prettier-ignore is inserted before the contiguous tag block."""
    description = "Fix rendering bug\n\nBUG=12345\nR=startblock\nMARKDOWN=true"
    result = _add_prettier_ignore_before_tags(description)
    assert result == (
        "Fix rendering bug\n\n<!-- prettier-ignore -->\nBUG=12345\nR=startblock\nMARKDOWN=true"
    )


def test_add_prettier_ignore_no_tags_unchanged() -> None:
    """Test that description without tags is returned unchanged."""
    description = "Fix rendering bug\n\nThis is just a description."
    result = _add_prettier_ignore_before_tags(description)
    assert result == description


def test_add_prettier_ignore_with_trailing_blank_lines() -> None:
    """Test that trailing blank lines don't prevent finding the tag block."""
    description = "Fix bug\n\nBUG=12345\nR=startblock\n\n"
    result = _add_prettier_ignore_before_tags(description)
    assert result == "Fix bug\n\n<!-- prettier-ignore -->\nBUG=12345\nR=startblock\n\n"


# === Tests for _strip_prettier_ignore ===


def test_strip_prettier_ignore_removes_comment() -> None:
    """Test that prettier-ignore comment lines are removed."""
    content = "Fix bug\n\n<!-- prettier-ignore -->\nBUG=12345\nR=startblock"
    result = _strip_prettier_ignore(content)
    assert result == "Fix bug\n\nBUG=12345\nR=startblock"


def test_strip_prettier_ignore_no_comment_unchanged() -> None:
    """Test that content without prettier-ignore is returned unchanged."""
    content = "Fix bug\n\nBUG=12345\nR=startblock"
    result = _strip_prettier_ignore(content)
    assert result == content


# === Tests for _fetch_cl_description ===


@patch("ace.handlers.reword.get_vcs_provider")
@patch("running_field.get_workspace_directory")
def test_fetch_cl_description_success(
    mock_get_ws: MagicMock, mock_get_provider: MagicMock
) -> None:
    """Test successful description fetch."""
    mock_get_ws.return_value = "/workspace"
    mock_provider = MagicMock()
    mock_provider.get_description.return_value = (True, "My CL description\n")
    mock_get_provider.return_value = mock_provider
    console = MagicMock()

    result = _fetch_cl_description("project", "cl/123", console)

    assert result == "My CL description\n"
    mock_provider.get_description.assert_called_once_with("cl/123", "/workspace")


@patch("running_field.get_workspace_directory")
def test_fetch_cl_description_workspace_error(
    mock_get_ws: MagicMock,
) -> None:
    """Test returns None when workspace lookup fails."""
    mock_get_ws.side_effect = RuntimeError("no workspace")
    console = MagicMock()

    result = _fetch_cl_description("project", "cl/123", console)

    assert result is None


@patch("ace.handlers.reword.get_vcs_provider")
@patch("running_field.get_workspace_directory")
def test_fetch_cl_description_cl_desc_fails(
    mock_get_ws: MagicMock, mock_get_provider: MagicMock
) -> None:
    """Test returns None when cl_desc command fails."""
    mock_get_ws.return_value = "/workspace"
    mock_provider = MagicMock()
    mock_provider.get_description.return_value = (False, "cl_desc failed")
    mock_get_provider.return_value = mock_provider
    console = MagicMock()

    result = _fetch_cl_description("project", "cl/123", console)

    assert result is None


@patch("ace.handlers.reword.get_vcs_provider")
@patch("running_field.get_workspace_directory")
def test_fetch_cl_description_command_not_found(
    mock_get_ws: MagicMock, mock_get_provider: MagicMock
) -> None:
    """Test returns None when cl_desc is not found."""
    mock_get_ws.return_value = "/workspace"
    mock_provider = MagicMock()
    mock_provider.get_description.return_value = (False, "cl_desc command not found")
    mock_get_provider.return_value = mock_provider
    console = MagicMock()

    result = _fetch_cl_description("project", "cl/123", console)

    assert result is None


# === Tests for _open_editor_with_content ===


@patch("ace.handlers.reword.get_editor", return_value="cat")
@patch("ace.handlers.reword.subprocess.run")
def test_open_editor_with_content_success(
    mock_run: MagicMock, _mock_editor: MagicMock
) -> None:
    """Test editor returns content on success."""
    mock_run.return_value = MagicMock(returncode=0)
    console = MagicMock()

    result = _open_editor_with_content("hello world", console)

    assert result == "hello world"


@patch("ace.handlers.reword.get_editor", return_value="false")
@patch("ace.handlers.reword.subprocess.run")
def test_open_editor_with_content_editor_fails(
    mock_run: MagicMock, _mock_editor: MagicMock
) -> None:
    """Test returns None when editor exits non-zero."""
    mock_run.return_value = MagicMock(returncode=1)
    console = MagicMock()

    result = _open_editor_with_content("hello", console)

    assert result is None


@patch("ace.handlers.reword.get_editor", return_value="cat")
@patch("ace.handlers.reword.subprocess.run")
def test_open_editor_with_content_cleans_up_temp_file(
    mock_run: MagicMock, _mock_editor: MagicMock
) -> None:
    """Test that temp file is cleaned up after editor."""
    temp_paths: list[str] = []

    def capture_run(cmd: list[str], **kwargs: object) -> MagicMock:
        if len(cmd) == 2:
            temp_paths.append(cmd[1])
        return MagicMock(returncode=0)

    mock_run.side_effect = capture_run
    console = MagicMock()

    _open_editor_with_content("test content", console)

    assert len(temp_paths) == 1
    assert not os.path.exists(temp_paths[0])


# === Tests for handle_reword ===


def _make_context_and_changespec(
    status: str = "WIP", cl: str | None = "123456"
) -> tuple[MagicMock, MagicMock]:
    """Create mock WorkflowContext and ChangeSpec."""
    ctx = MagicMock()
    ctx.console = MagicMock()

    cs = MagicMock()
    cs.status = status
    cs.cl = cl
    cs.name = "cl/test"
    cs.project_basename = "project"
    cs.file_path = "/path/to/project.gp"

    return ctx, cs


@patch("ace.changespec.get_base_status")
def test_handle_reword_invalid_status(mock_base: MagicMock) -> None:
    """Test reword rejected for invalid status."""
    mock_base.return_value = "Submitted"
    ctx, cs = _make_context_and_changespec(status="Submitted")

    handle_reword(ctx, cs)

    ctx.console.print.assert_called_once()
    assert "only available for" in ctx.console.print.call_args[0][0]


@patch("ace.changespec.get_base_status")
def test_handle_reword_no_cl(mock_base: MagicMock) -> None:
    """Test reword rejected when CL is not set."""
    mock_base.return_value = "WIP"
    ctx, cs = _make_context_and_changespec(cl=None)

    handle_reword(ctx, cs)

    assert "requires a CL" in ctx.console.print.call_args[0][0]


@patch("ace.handlers.reword._open_editor_with_content", return_value=None)
@patch(
    "ace.handlers.reword._fetch_cl_description",
    return_value="Original desc\n",
)
@patch("ace.changespec.get_base_status", return_value="WIP")
def test_handle_reword_editor_returns_none(
    _mock_base: MagicMock, _mock_fetch: MagicMock, _mock_editor: MagicMock
) -> None:
    """Test reword cancelled when editor returns None."""
    ctx, cs = _make_context_and_changespec()

    handle_reword(ctx, cs)

    assert "cancelled" in ctx.console.print.call_args[0][0].lower()


@patch("ace.handlers.reword._open_editor_with_content")
@patch("ace.handlers.reword._fetch_cl_description")
@patch("ace.changespec.get_base_status", return_value="Drafted")
def test_handle_reword_description_unchanged_no_workspace(
    _mock_base: MagicMock, mock_fetch: MagicMock, mock_editor: MagicMock
) -> None:
    """Test no workspace claimed when description is unchanged."""
    mock_fetch.return_value = "Same description\n"
    mock_editor.return_value = "Same description\n"
    ctx, cs = _make_context_and_changespec(status="Drafted")

    with patch("running_field.claim_workspace") as mock_claim:
        handle_reword(ctx, cs)
        mock_claim.assert_not_called()

    assert "unchanged" in ctx.console.print.call_args[0][0].lower()


@patch("ace.handlers.reword._open_editor_with_content")
@patch("ace.handlers.reword._fetch_cl_description")
@patch("ace.changespec.get_base_status", return_value="Drafted")
def test_handle_reword_trailing_newline_no_false_diff(
    _mock_base: MagicMock, mock_fetch: MagicMock, mock_editor: MagicMock
) -> None:
    """Test trailing newline differences don't trigger a reword."""
    mock_fetch.return_value = "Same description\n"
    mock_editor.return_value = "Same description"  # no trailing newline
    ctx, cs = _make_context_and_changespec(status="Drafted")

    with patch("running_field.claim_workspace") as mock_claim:
        handle_reword(ctx, cs)
        mock_claim.assert_not_called()


@patch("ace.handlers.reword._sync_description_after_reword")
@patch("ace.handlers.reword.get_vcs_provider")
@patch("ace.handlers.reword.run_bb_hg_clean", return_value=(True, None))
@patch(
    "running_field.get_workspace_directory_for_num",
    return_value=("/ws", "fig_101"),
)
@patch("running_field.claim_workspace", return_value=True)
@patch("running_field.get_first_available_axe_workspace", return_value=101)
@patch("running_field.release_workspace")
@patch(
    "ace.handlers.reword._open_editor_with_content",
    return_value="New description\n",
)
@patch(
    "ace.handlers.reword._fetch_cl_description",
    return_value="Old description\n",
)
@patch("ace.changespec.get_base_status", return_value="WIP")
def test_handle_reword_changed_runs_full_flow(
    _mock_base: MagicMock,
    _mock_fetch: MagicMock,
    _mock_editor: MagicMock,
    mock_release: MagicMock,
    _mock_first_ws: MagicMock,
    mock_claim: MagicMock,
    _mock_get_ws_dir: MagicMock,
    _mock_clean: MagicMock,
    mock_get_provider: MagicMock,
    mock_sync: MagicMock,
) -> None:
    """Test full reword flow when description is changed."""
    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)
    mock_provider.reword.return_value = (True, None)
    # prepare_description_for_reword passes description through (mock returns input)
    mock_provider.prepare_description_for_reword.side_effect = lambda d: d
    mock_get_provider.return_value = mock_provider
    ctx, cs = _make_context_and_changespec()

    handle_reword(ctx, cs)

    mock_claim.assert_called_once()
    # Verify prepare_description_for_reword was called with the edited description
    mock_provider.prepare_description_for_reword.assert_called_once_with(
        "New description\n"
    )
    # Verify provider.reword was called with the prepared description
    mock_provider.reword.assert_called_once_with("New description\n", "/ws")
    mock_sync.assert_called_once()
    mock_release.assert_called_once()


@patch("ace.handlers.reword._fetch_cl_description", return_value=None)
@patch("ace.changespec.get_base_status", return_value="WIP")
def test_handle_reword_fetch_fails_returns_early(
    _mock_base: MagicMock, _mock_fetch: MagicMock
) -> None:
    """Test early return when description fetch fails."""
    ctx, cs = _make_context_and_changespec()

    with patch("ace.handlers.reword._open_editor_with_content") as mock_editor:
        handle_reword(ctx, cs)
        mock_editor.assert_not_called()
