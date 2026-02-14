"""Tests for ace.changespec.structured_updates module."""

import pytest
from ace.changespec.models import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    MentorEntry,
)
from ace.changespec.project_spec import ProjectSpec, WorkspaceClaim
from ace.changespec.structured_updates import (
    _find_changespec,
    _replace_changespec,
    add_changespec_commit_entry,
    add_running_claim,
    remove_running_claim,
    update_changespec_cl,
    update_changespec_comments,
    update_changespec_description,
    update_changespec_hooks,
    update_changespec_mentors,
    update_changespec_parent,
    update_changespec_status,
    update_commit_entry_suffix,
    update_parent_references,
)


def _make_cs(
    name: str = "test_cs",
    status: str = "WIP",
    **kwargs: object,
) -> ChangeSpec:
    """Create a ChangeSpec with sensible defaults for testing."""
    defaults: dict[str, object] = {
        "description": "Test description",
        "parent": None,
        "cl": None,
        "test_targets": None,
        "kickstart": None,
        "file_path": "/tmp/test.gp",
        "line_number": 1,
    }
    defaults.update(kwargs)
    return ChangeSpec(name=name, status=status, **defaults)  # type: ignore[arg-type]


def _make_spec(
    changespecs: list[ChangeSpec] | None = None,
    **kwargs: object,
) -> ProjectSpec:
    """Create a ProjectSpec with sensible defaults for testing."""
    defaults: dict[str, object] = {"file_path": "/tmp/test.gp"}
    defaults.update(kwargs)
    return ProjectSpec(changespecs=changespecs, **defaults)  # type: ignore[arg-type]


# --- _find_changespec tests ---


def test_find_changespec_found() -> None:
    cs = _make_cs(name="foo")
    spec = _make_spec(changespecs=[cs])
    idx, found = _find_changespec(spec, "foo")
    assert idx == 0
    assert found is cs


def test_find_changespec_not_found() -> None:
    cs = _make_cs(name="foo")
    spec = _make_spec(changespecs=[cs])
    with pytest.raises(ValueError, match="not found"):
        _find_changespec(spec, "bar")


def test_find_changespec_error_lists_available() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="alpha"), _make_cs(name="beta")])
    with pytest.raises(ValueError, match="alpha, beta"):
        _find_changespec(spec, "missing")


def test_find_changespec_empty_list() -> None:
    spec = _make_spec(changespecs=[])
    with pytest.raises(ValueError, match="none"):
        _find_changespec(spec, "any")


def test_find_changespec_none_list() -> None:
    spec = _make_spec(changespecs=None)
    with pytest.raises(ValueError, match="none"):
        _find_changespec(spec, "any")


def test_find_changespec_multiple_specs() -> None:
    cs_a = _make_cs(name="alpha")
    cs_b = _make_cs(name="beta")
    spec = _make_spec(changespecs=[cs_a, cs_b])
    idx, found = _find_changespec(spec, "beta")
    assert idx == 1
    assert found is cs_b


# --- _replace_changespec tests ---


def test_replace_changespec_immutability() -> None:
    cs_old = _make_cs(name="foo", status="WIP")
    cs_new = _make_cs(name="foo", status="Drafted")
    spec = _make_spec(changespecs=[cs_old])
    result = _replace_changespec(spec, 0, cs_new)
    assert result.changespecs is not None
    assert result.changespecs[0].status == "Drafted"
    assert spec.changespecs is not None
    assert spec.changespecs[0].status == "WIP"


# --- update_changespec_status tests ---


def test_update_changespec_status_happy() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", status="WIP")])
    result = update_changespec_status(spec, "foo", "Drafted")
    assert result.changespecs is not None
    assert result.changespecs[0].status == "Drafted"


def test_update_changespec_status_immutability() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", status="WIP")])
    result = update_changespec_status(spec, "foo", "Drafted")
    assert spec.changespecs is not None
    assert spec.changespecs[0].status == "WIP"
    assert result is not spec


def test_update_changespec_status_not_found() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo")])
    with pytest.raises(ValueError, match="not found"):
        update_changespec_status(spec, "missing", "Drafted")


# --- update_changespec_cl tests ---


def test_update_changespec_cl_happy() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", cl=None)])
    result = update_changespec_cl(spec, "foo", "http://cl/123")
    assert result.changespecs is not None
    assert result.changespecs[0].cl == "http://cl/123"


def test_update_changespec_cl_clear() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", cl="http://cl/123")])
    result = update_changespec_cl(spec, "foo", None)
    assert result.changespecs is not None
    assert result.changespecs[0].cl is None


def test_update_changespec_cl_immutability() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", cl="old")])
    result = update_changespec_cl(spec, "foo", "new")
    assert spec.changespecs is not None
    assert spec.changespecs[0].cl == "old"
    assert result is not spec


# --- update_changespec_parent tests ---


def test_update_changespec_parent_happy() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", parent=None)])
    result = update_changespec_parent(spec, "foo", "bar")
    assert result.changespecs is not None
    assert result.changespecs[0].parent == "bar"


def test_update_changespec_parent_clear() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", parent="bar")])
    result = update_changespec_parent(spec, "foo", None)
    assert result.changespecs is not None
    assert result.changespecs[0].parent is None


# --- update_changespec_description tests ---


def test_update_changespec_description_happy() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", description="old")])
    result = update_changespec_description(spec, "foo", "new desc")
    assert result.changespecs is not None
    assert result.changespecs[0].description == "new desc"


def test_update_changespec_description_immutability() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", description="old")])
    update_changespec_description(spec, "foo", "new")
    assert spec.changespecs is not None
    assert spec.changespecs[0].description == "old"


# --- update_changespec_hooks tests ---


def test_update_changespec_hooks_happy() -> None:
    hooks = [HookEntry(command="lint")]
    spec = _make_spec(changespecs=[_make_cs(name="foo")])
    result = update_changespec_hooks(spec, "foo", hooks)
    assert result.changespecs is not None
    assert result.changespecs[0].hooks is not None
    assert len(result.changespecs[0].hooks) == 1
    assert result.changespecs[0].hooks[0].command == "lint"


def test_update_changespec_hooks_clear() -> None:
    hooks = [HookEntry(command="lint")]
    spec = _make_spec(changespecs=[_make_cs(name="foo", hooks=hooks)])
    result = update_changespec_hooks(spec, "foo", None)
    assert result.changespecs is not None
    assert result.changespecs[0].hooks is None


def test_update_changespec_hooks_immutability() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo")])
    update_changespec_hooks(spec, "foo", [HookEntry(command="lint")])
    assert spec.changespecs is not None
    assert spec.changespecs[0].hooks is None


# --- update_changespec_comments tests ---


def test_update_changespec_comments_happy() -> None:
    comments = [CommentEntry(reviewer="critique", file_path="/tmp/c.json")]
    spec = _make_spec(changespecs=[_make_cs(name="foo")])
    result = update_changespec_comments(spec, "foo", comments)
    assert result.changespecs is not None
    assert result.changespecs[0].comments is not None
    assert len(result.changespecs[0].comments) == 1


def test_update_changespec_comments_clear() -> None:
    comments = [CommentEntry(reviewer="critique", file_path="/tmp/c.json")]
    spec = _make_spec(changespecs=[_make_cs(name="foo", comments=comments)])
    result = update_changespec_comments(spec, "foo", None)
    assert result.changespecs is not None
    assert result.changespecs[0].comments is None


# --- update_changespec_mentors tests ---


def test_update_changespec_mentors_happy() -> None:
    mentors = [MentorEntry(entry_id="1", profiles=["default"])]
    spec = _make_spec(changespecs=[_make_cs(name="foo")])
    result = update_changespec_mentors(spec, "foo", mentors)
    assert result.changespecs is not None
    assert result.changespecs[0].mentors is not None
    assert len(result.changespecs[0].mentors) == 1


def test_update_changespec_mentors_clear() -> None:
    mentors = [MentorEntry(entry_id="1", profiles=["default"])]
    spec = _make_spec(changespecs=[_make_cs(name="foo", mentors=mentors)])
    result = update_changespec_mentors(spec, "foo", None)
    assert result.changespecs is not None
    assert result.changespecs[0].mentors is None


# --- add_changespec_commit_entry tests ---


def test_add_commit_entry_append() -> None:
    existing = CommitEntry(number=1, note="First")
    new_entry = CommitEntry(number=2, note="Second")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[existing])])
    result = add_changespec_commit_entry(spec, "foo", new_entry)
    assert result.changespecs is not None
    assert len(result.changespecs[0].commits or []) == 2
    assert result.changespecs[0].commits[1].note == "Second"  # type: ignore[index]


def test_add_commit_entry_init_from_none() -> None:
    entry = CommitEntry(number=1, note="First")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=None)])
    result = add_changespec_commit_entry(spec, "foo", entry)
    assert result.changespecs is not None
    assert len(result.changespecs[0].commits or []) == 1


def test_add_commit_entry_immutability() -> None:
    existing = CommitEntry(number=1, note="First")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[existing])])
    add_changespec_commit_entry(spec, "foo", CommitEntry(number=2, note="Second"))
    assert spec.changespecs is not None
    assert len(spec.changespecs[0].commits or []) == 1


# --- update_commit_entry_suffix tests ---


def test_update_commit_entry_suffix_basic() -> None:
    entry = CommitEntry(number=1, note="First")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[entry])])
    result = update_commit_entry_suffix(spec, "foo", "1", "NEW PROPOSAL", "error")
    assert result.changespecs is not None
    commit = result.changespecs[0].commits[0]  # type: ignore[index]
    assert commit.suffix == "NEW PROPOSAL"
    assert commit.suffix_type == "error"


def test_update_commit_entry_suffix_proposal_entry() -> None:
    entry = CommitEntry(number=1, note="Fix", proposal_letter="a")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[entry])])
    result = update_commit_entry_suffix(spec, "foo", "1a", "done", "plain")
    assert result.changespecs is not None
    commit = result.changespecs[0].commits[0]  # type: ignore[index]
    assert commit.suffix == "done"


def test_update_commit_entry_suffix_clear_to_none() -> None:
    entry = CommitEntry(number=1, note="First", suffix="old", suffix_type="error")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[entry])])
    result = update_commit_entry_suffix(spec, "foo", "1", None, None)
    assert result.changespecs is not None
    commit = result.changespecs[0].commits[0]  # type: ignore[index]
    assert commit.suffix is None
    assert commit.suffix_type is None


def test_update_commit_entry_suffix_no_commits_raises() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=None)])
    with pytest.raises(ValueError, match="has no commits"):
        update_commit_entry_suffix(spec, "foo", "1", "x", None)


def test_update_commit_entry_suffix_entry_not_found_raises() -> None:
    entry = CommitEntry(number=1, note="First")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[entry])])
    with pytest.raises(ValueError, match="not found"):
        update_commit_entry_suffix(spec, "foo", "99", "x", None)


def test_update_commit_entry_suffix_immutability() -> None:
    entry = CommitEntry(number=1, note="First")
    spec = _make_spec(changespecs=[_make_cs(name="foo", commits=[entry])])
    update_commit_entry_suffix(spec, "foo", "1", "NEW", "error")
    assert spec.changespecs is not None
    assert spec.changespecs[0].commits[0].suffix is None  # type: ignore[index]


# --- add_running_claim tests ---


def test_add_running_claim_to_empty() -> None:
    spec = _make_spec(running=None)
    claim = WorkspaceClaim(workspace_num=1, pid=100, workflow="fix")
    result = add_running_claim(spec, claim)
    assert result.running is not None
    assert len(result.running) == 1
    assert result.running[0].workspace_num == 1


def test_add_running_claim_to_existing() -> None:
    existing = WorkspaceClaim(workspace_num=1, pid=100, workflow="fix")
    spec = _make_spec(running=[existing])
    new_claim = WorkspaceClaim(workspace_num=2, pid=200, workflow="submit")
    result = add_running_claim(spec, new_claim)
    assert result.running is not None
    assert len(result.running) == 2


def test_add_running_claim_immutability() -> None:
    existing = WorkspaceClaim(workspace_num=1, pid=100, workflow="fix")
    spec = _make_spec(running=[existing])
    add_running_claim(spec, WorkspaceClaim(workspace_num=2, pid=200, workflow="submit"))
    assert spec.running is not None
    assert len(spec.running) == 1


# --- remove_running_claim tests ---


def test_remove_running_claim_by_workspace_num() -> None:
    claims = [
        WorkspaceClaim(workspace_num=1, pid=100, workflow="fix"),
        WorkspaceClaim(workspace_num=2, pid=200, workflow="submit"),
    ]
    spec = _make_spec(running=claims)
    result = remove_running_claim(spec, workspace_num=1)
    assert result.running is not None
    assert len(result.running) == 1
    assert result.running[0].workspace_num == 2


def test_remove_running_claim_with_workflow_filter() -> None:
    claims = [
        WorkspaceClaim(workspace_num=1, pid=100, workflow="fix"),
        WorkspaceClaim(workspace_num=1, pid=200, workflow="submit"),
    ]
    spec = _make_spec(running=claims)
    result = remove_running_claim(spec, workspace_num=1, workflow="fix")
    assert result.running is not None
    assert len(result.running) == 1
    assert result.running[0].workflow == "submit"


def test_remove_running_claim_last_sets_none() -> None:
    claims = [WorkspaceClaim(workspace_num=1, pid=100, workflow="fix")]
    spec = _make_spec(running=claims)
    result = remove_running_claim(spec, workspace_num=1)
    assert result.running is None


def test_remove_running_claim_no_match_unchanged() -> None:
    claims = [WorkspaceClaim(workspace_num=1, pid=100, workflow="fix")]
    spec = _make_spec(running=claims)
    result = remove_running_claim(spec, workspace_num=99)
    assert result is spec


def test_remove_running_claim_none_running_unchanged() -> None:
    spec = _make_spec(running=None)
    result = remove_running_claim(spec, workspace_num=1)
    assert result is spec


# --- update_parent_references tests ---


def test_update_parent_references_basic() -> None:
    spec = _make_spec(
        changespecs=[
            _make_cs(name="child", parent="old_parent"),
            _make_cs(name="old_parent"),
        ]
    )
    result = update_parent_references(spec, "old_parent", "new_parent")
    assert result.changespecs is not None
    assert result.changespecs[0].parent == "new_parent"
    assert result.changespecs[1].parent is None


def test_update_parent_references_multiple_matches() -> None:
    spec = _make_spec(
        changespecs=[
            _make_cs(name="a", parent="shared"),
            _make_cs(name="b", parent="shared"),
            _make_cs(name="c", parent="other"),
        ]
    )
    result = update_parent_references(spec, "shared", "renamed")
    assert result.changespecs is not None
    assert result.changespecs[0].parent == "renamed"
    assert result.changespecs[1].parent == "renamed"
    assert result.changespecs[2].parent == "other"


def test_update_parent_references_no_match_unchanged() -> None:
    spec = _make_spec(changespecs=[_make_cs(name="foo", parent="bar")])
    result = update_parent_references(spec, "nonexistent", "new")
    assert result is spec


def test_update_parent_references_none_changespecs_unchanged() -> None:
    spec = _make_spec(changespecs=None)
    result = update_parent_references(spec, "old", "new")
    assert result is spec
