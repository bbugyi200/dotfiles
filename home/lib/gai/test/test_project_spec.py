"""Tests for ProjectSpec and WorkspaceClaim data models and JSON schema."""

import json
from pathlib import Path

import pytest
from ace.changespec.models import ChangeSpec
from ace.changespec.project_spec import ProjectSpec, WorkspaceClaim
from jsonschema import ValidationError, validate  # type: ignore[import-untyped]


def _load_schema() -> dict:  # type: ignore[type-arg]
    """Load the project_spec JSON schema."""
    schema_path = Path(__file__).parent.parent / "xprompts" / "project_spec.schema.json"
    with open(schema_path) as f:
        return json.load(f)  # type: ignore[no-any-return]


# --- WorkspaceClaim construction tests ---


def test_workspace_claim_all_fields() -> None:
    """Test WorkspaceClaim with all fields specified."""
    claim = WorkspaceClaim(
        workspace_num=1,
        pid=12345,
        workflow="fix_hook",
        cl_name="my-feature",
        artifacts_timestamp="260214_103000",
    )
    assert claim.workspace_num == 1
    assert claim.pid == 12345
    assert claim.workflow == "fix_hook"
    assert claim.cl_name == "my-feature"
    assert claim.artifacts_timestamp == "260214_103000"


def test_workspace_claim_defaults_only() -> None:
    """Test WorkspaceClaim with only required fields."""
    claim = WorkspaceClaim(workspace_num=2, pid=99999, workflow="summarize")
    assert claim.workspace_num == 2
    assert claim.pid == 99999
    assert claim.workflow == "summarize"
    assert claim.cl_name is None
    assert claim.artifacts_timestamp is None


# --- ProjectSpec construction tests ---


def test_project_spec_all_fields() -> None:
    """Test ProjectSpec with all fields specified."""
    claim = WorkspaceClaim(workspace_num=1, pid=100, workflow="fix_hook")
    cs = ChangeSpec(
        name="my-cl",
        description="A change",
        parent=None,
        cl="12345",
        status="WIP",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=10,
    )
    spec = ProjectSpec(
        file_path="/tmp/test.gp",
        bug="b/123",
        running=[claim],
        changespecs=[cs],
    )
    assert spec.file_path == "/tmp/test.gp"
    assert spec.bug == "b/123"
    assert spec.running == [claim]
    assert spec.changespecs == [cs]


def test_project_spec_defaults() -> None:
    """Test ProjectSpec with only required fields."""
    spec = ProjectSpec(file_path="/tmp/test.gp")
    assert spec.file_path == "/tmp/test.gp"
    assert spec.bug is None
    assert spec.running is None
    assert spec.changespecs is None


def test_project_spec_multiple_changespecs() -> None:
    """Test ProjectSpec with multiple ChangeSpecs."""
    cs1 = ChangeSpec(
        name="cl-1",
        description="First",
        parent=None,
        cl=None,
        status="WIP",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=5,
    )
    cs2 = ChangeSpec(
        name="cl-2",
        description="Second",
        parent="cl-1",
        cl="99",
        status="Drafted",
        test_targets=["//test:foo"],
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=20,
    )
    spec = ProjectSpec(file_path="/tmp/test.gp", changespecs=[cs1, cs2])
    assert spec.changespecs is not None
    assert len(spec.changespecs) == 2
    assert spec.changespecs[0].name == "cl-1"
    assert spec.changespecs[1].name == "cl-2"


# --- Schema validation tests ---


def test_schema_minimal_valid() -> None:
    """Test that a minimal empty object is valid."""
    schema = _load_schema()
    validate(instance={}, schema=schema)


def test_schema_full_valid() -> None:
    """Test that a fully populated document is valid."""
    schema = _load_schema()
    doc = {
        "bug": "b/123456",
        "running": [
            {
                "workspace_num": 1,
                "pid": 12345,
                "workflow": "fix_hook",
                "cl_name": "my-feature",
                "artifacts_timestamp": "260214_103000",
            }
        ],
        "changespecs": [
            {
                "name": "my-cl",
                "description": "Add foobar feature",
                "status": "WIP",
                "parent": None,
                "cl": "12345",
                "bug": None,
                "test_targets": ["//test:foo"],
                "kickstart": None,
                "commits": [
                    {
                        "number": 1,
                        "note": "Initial commit",
                        "suffix_type": "error",
                    }
                ],
                "hooks": [
                    {
                        "command": "!$bb_presubmit",
                        "status_lines": [
                            {
                                "commit_entry_num": "1",
                                "timestamp": "260214_103000",
                                "status": "PASSED",
                                "duration": "1m23s",
                            }
                        ],
                    }
                ],
                "comments": [
                    {
                        "reviewer": "critique",
                        "file_path": "~/.gai/comments/test.json",
                    }
                ],
                "mentors": [
                    {
                        "entry_id": "1",
                        "profiles": ["default"],
                        "status_lines": [
                            {
                                "profile_name": "default",
                                "mentor_name": "review",
                                "status": "PASSED",
                                "timestamp": "260214_103000",
                                "duration": "0h2m15s",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    validate(instance=doc, schema=schema)


def test_schema_rejects_unknown_top_level_props() -> None:
    """Test that unknown top-level properties are rejected."""
    schema = _load_schema()
    with pytest.raises(ValidationError):
        validate(instance={"unknown_field": "value"}, schema=schema)


def test_schema_rejects_missing_required_in_changespec() -> None:
    """Test that changespecs missing required fields are rejected."""
    schema = _load_schema()
    with pytest.raises(ValidationError):
        validate(
            instance={"changespecs": [{"name": "foo"}]},
            schema=schema,
        )


def test_schema_rejects_missing_required_in_workspace_claim() -> None:
    """Test that workspace claims missing required fields are rejected."""
    schema = _load_schema()
    with pytest.raises(ValidationError):
        validate(
            instance={"running": [{"workspace_num": 1}]},
            schema=schema,
        )


def test_schema_accepts_null_optional_fields() -> None:
    """Test that null values are accepted for optional fields."""
    schema = _load_schema()
    doc = {
        "bug": None,
        "changespecs": [
            {
                "name": "test",
                "description": "A test",
                "status": "WIP",
                "parent": None,
                "cl": None,
                "bug": None,
                "test_targets": None,
                "kickstart": None,
                "commits": None,
                "hooks": None,
                "comments": None,
                "mentors": None,
            }
        ],
    }
    validate(instance=doc, schema=schema)
