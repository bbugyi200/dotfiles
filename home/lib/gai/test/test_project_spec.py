"""Tests for ProjectSpec and WorkspaceClaim data models and JSON schema."""

import json
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from ace.changespec.models import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
)
from ace.changespec.project_spec import (
    ProjectSpec,
    WorkspaceClaim,
    _dict_to_project_spec,
    _project_spec_to_dict,
    parse_project_spec,
    read_and_update_project_spec,
    serialize_project_spec,
    write_project_spec_atomic,
)
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


# --- Serialize / Parse tests ---


def _make_full_spec(file_path: str) -> ProjectSpec:
    """Build a fully populated ProjectSpec for testing."""
    return ProjectSpec(
        file_path=file_path,
        bug="b/123",
        running=[
            WorkspaceClaim(
                workspace_num=1,
                pid=12345,
                workflow="fix_hook",
                cl_name="my-cl",
                artifacts_timestamp="260214_103000",
            ),
        ],
        changespecs=[
            ChangeSpec(
                name="my-cl",
                description="Add foobar feature",
                parent=None,
                cl="12345",
                status="WIP",
                test_targets=["//test:foo"],
                kickstart=None,
                file_path=file_path,
                line_number=0,
                bug="b/456",
                commits=[
                    CommitEntry(number=1, note="Initial commit"),
                    CommitEntry(
                        number=1,
                        note="Revised",
                        proposal_letter="a",
                        suffix="NEW PROPOSAL",
                        suffix_type="error",
                    ),
                ],
                hooks=[
                    HookEntry(
                        command="!$bb_presubmit",
                        status_lines=[
                            HookStatusLine(
                                commit_entry_num="1",
                                timestamp="260214_103000",
                                status="PASSED",
                                duration="1m23s",
                            )
                        ],
                    )
                ],
                comments=[
                    CommentEntry(
                        reviewer="critique",
                        file_path="~/.gai/comments/test.json",
                    )
                ],
                mentors=[
                    MentorEntry(
                        entry_id="1",
                        profiles=["default"],
                        status_lines=[
                            MentorStatusLine(
                                profile_name="default",
                                mentor_name="review",
                                status="PASSED",
                                timestamp="260214_103000",
                                duration="0h2m15s",
                            )
                        ],
                    )
                ],
            ),
        ],
    )


def test_serialize_round_trip(tmp_path: Path) -> None:
    """Build a full ProjectSpec, serialize, write, parse back, assert equality."""
    yaml_file = str(tmp_path / "test.yaml")
    spec = _make_full_spec(yaml_file)

    # Serialize → write → parse
    content = serialize_project_spec(spec)
    Path(yaml_file).write_text(content)
    parsed = parse_project_spec(yaml_file)

    assert parsed == spec


def test_serialize_minimal_round_trip(tmp_path: Path) -> None:
    """Empty ProjectSpec round-trips correctly."""
    yaml_file = str(tmp_path / "minimal.yaml")
    spec = ProjectSpec(file_path=yaml_file)

    content = serialize_project_spec(spec)
    Path(yaml_file).write_text(content)
    parsed = parse_project_spec(yaml_file)

    assert parsed.file_path == yaml_file
    assert parsed.bug is None
    assert parsed.running is None
    assert parsed.changespecs is None


def test_parse_empty_file(tmp_path: Path) -> None:
    """Parse an empty YAML file returns empty ProjectSpec."""
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("")

    parsed = parse_project_spec(str(yaml_file))

    assert parsed.file_path == str(yaml_file)
    assert parsed.bug is None
    assert parsed.running is None
    assert parsed.changespecs is None


def test_parse_full_yaml(tmp_path: Path) -> None:
    """Parse a YAML string with all fields and verify dataclass fields."""
    yaml_file = tmp_path / "full.yaml"
    doc = {
        "bug": "b/999",
        "running": [
            {"workspace_num": 2, "pid": 555, "workflow": "crs", "cl_name": "feat-x"}
        ],
        "changespecs": [
            {
                "name": "feat-x",
                "description": "A feature",
                "status": "Drafted",
                "parent": "base-cl",
                "cl": "77777",
                "bug": "b/888",
                "test_targets": ["//a:test", "//b:test"],
                "kickstart": "make build",
                "commits": [
                    {"number": 1, "note": "First", "chat": "chat1", "diff": "diff1"},
                    {
                        "number": 2,
                        "note": "Second",
                        "proposal_letter": "a",
                        "suffix": "ZOMBIE",
                        "suffix_type": "error",
                    },
                ],
                "hooks": [
                    {
                        "command": "$run_tests",
                        "status_lines": [
                            {
                                "commit_entry_num": "1",
                                "timestamp": "260214_120000",
                                "status": "RUNNING",
                            },
                            {
                                "commit_entry_num": "2",
                                "timestamp": "260214_130000",
                                "status": "PASSED",
                                "duration": "5m10s",
                                "summary": "All tests pass",
                            },
                        ],
                    }
                ],
                "comments": [
                    {
                        "reviewer": "critique",
                        "file_path": "~/.gai/comments/feat-x.json",
                        "suffix": "Unresolved Critique Comments",
                        "suffix_type": "error",
                    }
                ],
                "mentors": [
                    {
                        "entry_id": "1",
                        "profiles": ["default", "security"],
                        "is_wip": True,
                        "status_lines": [
                            {
                                "profile_name": "default",
                                "mentor_name": "review",
                                "status": "FAILED",
                                "timestamp": "260214_140000",
                                "duration": "1h0m5s",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    yaml_file.write_text(yaml.dump(doc, default_flow_style=False))

    parsed = parse_project_spec(str(yaml_file))

    assert parsed.bug == "b/999"
    assert parsed.running is not None
    assert len(parsed.running) == 1
    assert parsed.running[0].workspace_num == 2
    assert parsed.running[0].cl_name == "feat-x"

    assert parsed.changespecs is not None
    cs = parsed.changespecs[0]
    assert cs.name == "feat-x"
    assert cs.description == "A feature"
    assert cs.status == "Drafted"
    assert cs.parent == "base-cl"
    assert cs.cl == "77777"
    assert cs.bug == "b/888"
    assert cs.test_targets == ["//a:test", "//b:test"]
    assert cs.kickstart == "make build"
    assert cs.file_path == str(yaml_file)
    assert cs.line_number == 0

    # Commits
    assert cs.commits is not None
    assert len(cs.commits) == 2
    assert cs.commits[0].number == 1
    assert cs.commits[0].chat == "chat1"
    assert cs.commits[1].proposal_letter == "a"
    assert cs.commits[1].suffix_type == "error"

    # Hooks
    assert cs.hooks is not None
    assert cs.hooks[0].command == "$run_tests"
    assert cs.hooks[0].status_lines is not None
    assert len(cs.hooks[0].status_lines) == 2
    assert cs.hooks[0].status_lines[1].summary == "All tests pass"

    # Comments
    assert cs.comments is not None
    assert cs.comments[0].suffix == "Unresolved Critique Comments"

    # Mentors
    assert cs.mentors is not None
    assert cs.mentors[0].is_wip is True
    assert cs.mentors[0].profiles == ["default", "security"]
    assert cs.mentors[0].status_lines is not None
    assert cs.mentors[0].status_lines[0].status == "FAILED"


def test_parse_validates_schema(tmp_path: Path) -> None:
    """Invalid YAML data raises ValidationError."""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text(yaml.dump({"unknown_field": "bad"}))

    with pytest.raises(ValidationError):
        parse_project_spec(str(yaml_file))


def test_write_project_spec_atomic(tmp_path: Path) -> None:
    """write_project_spec_atomic writes content that can be parsed back."""
    yaml_file = str(tmp_path / "atomic.yaml")
    spec = _make_full_spec(yaml_file)

    write_project_spec_atomic(yaml_file, spec, "test commit")

    parsed = parse_project_spec(yaml_file)
    assert parsed == spec


def test_read_and_update_project_spec(tmp_path: Path) -> None:
    """Context manager reads, allows mutation, and writes back."""
    yaml_file = str(tmp_path / "update.yaml")

    # Create initial file
    initial = ProjectSpec(
        file_path=yaml_file,
        bug="b/100",
        changespecs=[
            ChangeSpec(
                name="cl-1",
                description="Original",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=yaml_file,
                line_number=0,
            )
        ],
    )
    write_project_spec_atomic(yaml_file, initial, "init")

    # Mutate via context manager
    with read_and_update_project_spec(yaml_file, "update bug") as spec:
        spec.bug = "b/200"
        assert spec.changespecs is not None
        spec.changespecs[0].description = "Modified"

    # Verify changes persisted
    result = parse_project_spec(yaml_file)
    assert result.bug == "b/200"
    assert result.changespecs is not None
    assert result.changespecs[0].description == "Modified"


def test_none_fields_omitted_in_yaml() -> None:
    """Serialize ProjectSpec with None fields — verify absent from YAML output."""
    spec = ProjectSpec(
        file_path="/tmp/test.yaml",
        bug=None,
        running=None,
        changespecs=[
            ChangeSpec(
                name="cl-1",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path="/tmp/test.yaml",
                line_number=0,
                bug=None,
                commits=None,
                hooks=None,
                comments=None,
                mentors=None,
            )
        ],
    )
    yaml_str = serialize_project_spec(spec)
    data = yaml.safe_load(yaml_str)

    # Top-level None fields omitted
    assert "bug" not in data
    assert "running" not in data

    # ChangeSpec None fields omitted
    cs = data["changespecs"][0]
    assert "parent" not in cs
    assert "cl" not in cs
    assert "bug" not in cs
    assert "test_targets" not in cs
    assert "kickstart" not in cs
    assert "commits" not in cs
    assert "hooks" not in cs
    assert "comments" not in cs
    assert "mentors" not in cs

    # Metadata fields excluded
    assert "file_path" not in data
    assert "file_path" not in cs
    assert "line_number" not in cs


def test_project_spec_to_dict_excludes_metadata() -> None:
    """_project_spec_to_dict excludes file_path and line_number."""
    spec = ProjectSpec(
        file_path="/tmp/test.yaml",
        changespecs=[
            ChangeSpec(
                name="x",
                description="d",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path="/tmp/test.yaml",
                line_number=42,
            )
        ],
    )
    d = _project_spec_to_dict(spec)

    assert "file_path" not in d
    cs = d["changespecs"][0]
    assert "file_path" not in cs
    assert "line_number" not in cs


def test_dict_to_project_spec_sets_metadata() -> None:
    """_dict_to_project_spec sets file_path and line_number=0."""
    data = {
        "bug": "b/1",
        "changespecs": [{"name": "a", "description": "b", "status": "WIP"}],
    }
    spec = _dict_to_project_spec(data, "/my/file.yaml")

    assert spec.file_path == "/my/file.yaml"
    assert spec.changespecs is not None
    assert spec.changespecs[0].file_path == "/my/file.yaml"
    assert spec.changespecs[0].line_number == 0
