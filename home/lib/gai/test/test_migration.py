"""Tests for .gp-to-YAML conversion logic."""

import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from ace.changespec.project_spec import (
    WorkspaceClaim,
    convert_gp_to_project_spec,
    parse_project_spec,
    serialize_project_spec,
)
from jsonschema import validate  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Sample .gp content constants
# ---------------------------------------------------------------------------

GP_BASIC = """\
## ChangeSpec
NAME: my-feature
DESCRIPTION:
  Add a new widget
STATUS: WIP
"""

GP_WITH_BUG = """\
## ChangeSpec
NAME: bugfix-cl
DESCRIPTION:
  Fix the crash on startup
BUG: b/123456
STATUS: Drafted
"""

GP_WITH_RUNNING = """\
RUNNING:
  #1 | 99999 | crs | run-cl
  #3 | 88888 | fix_hook | run-cl | 260214_103000

## ChangeSpec
NAME: run-cl
DESCRIPTION:
  Running test
STATUS: WIP
"""

GP_MULTIPLE_CS = """\
## ChangeSpec
NAME: cl-alpha
DESCRIPTION:
  First change
STATUS: WIP

## ChangeSpec
NAME: cl-beta
DESCRIPTION:
  Second change
PARENT: cl-alpha
STATUS: Drafted
CL: 77777
"""

GP_FULL = """\
RUNNING:
  #2 | 55555 | crs | full-cl

## ChangeSpec
NAME: full-cl
DESCRIPTION:
  A fully-populated ChangeSpec
BUG: b/999
STATUS: WIP
PARENT: base-cl
CL: 12345
TEST TARGETS:
  //test:foo
  //test:bar
COMMITS:
  (1) Initial implementation
  (2) Address review feedback
HOOKS:
  !$bb_presubmit
COMMENTS:
  [critique] ~/.gai/comments/full-cl-critique-260214_100000.json
MENTORS:
  (1) default
"""

GP_EMPTY = ""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _write_gp(tmp_path: Path, content: str) -> tuple[str, str]:
    """Write a .gp file and return (gp_path, yaml_path) as strings."""
    gp_file = tmp_path / "test.gp"
    gp_file.write_text(content)
    yaml_file = tmp_path / "test.yaml"
    return str(gp_file), str(yaml_file)


def test_convert_gp_basic(tmp_path: Path) -> None:
    """Minimal .gp with one ChangeSpec converts correctly."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_BASIC)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.file_path == yaml_path
    assert spec.bug is None
    assert spec.running is None
    assert spec.changespecs is not None
    assert len(spec.changespecs) == 1
    cs = spec.changespecs[0]
    assert cs.name == "my-feature"
    assert cs.description == "Add a new widget"
    assert cs.status == "WIP"


def test_convert_gp_with_bug(tmp_path: Path) -> None:
    """BUG field extracted to top-level ProjectSpec.bug."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_WITH_BUG)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.bug == "b/123456"
    assert spec.changespecs is not None
    # Per-CS bug is also preserved
    assert spec.changespecs[0].bug == "b/123456"


def test_convert_gp_with_running(tmp_path: Path) -> None:
    """RUNNING field with workspace claims mapped correctly."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_WITH_RUNNING)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.running is not None
    assert len(spec.running) == 2

    claim1 = spec.running[0]
    assert isinstance(claim1, WorkspaceClaim)
    assert claim1.workspace_num == 1
    assert claim1.pid == 99999
    assert claim1.workflow == "crs"
    assert claim1.cl_name == "run-cl"
    assert claim1.artifacts_timestamp is None

    claim2 = spec.running[1]
    assert claim2.workspace_num == 3
    assert claim2.pid == 88888
    assert claim2.workflow == "fix_hook"
    assert claim2.artifacts_timestamp == "260214_103000"


def test_convert_gp_with_multiple_changespecs(tmp_path: Path) -> None:
    """Multiple ChangeSpecs all present in output."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_MULTIPLE_CS)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.changespecs is not None
    assert len(spec.changespecs) == 2
    assert spec.changespecs[0].name == "cl-alpha"
    assert spec.changespecs[0].status == "WIP"
    assert spec.changespecs[1].name == "cl-beta"
    assert spec.changespecs[1].parent == "cl-alpha"
    assert spec.changespecs[1].cl == "77777"


def test_convert_gp_full_round_trip(tmp_path: Path) -> None:
    """All fields survive convert → serialize → write → parse back."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_FULL)

    original = convert_gp_to_project_spec(gp_path, yaml_path)

    # Serialize → write → parse
    content = serialize_project_spec(original)
    Path(yaml_path).write_text(content)
    parsed = parse_project_spec(yaml_path)

    # Top-level fields
    assert parsed.bug == original.bug
    assert parsed.file_path == yaml_path

    # Running
    assert parsed.running is not None
    assert original.running is not None
    assert len(parsed.running) == len(original.running)
    assert parsed.running[0].workspace_num == original.running[0].workspace_num
    assert parsed.running[0].pid == original.running[0].pid

    # ChangeSpecs
    assert parsed.changespecs is not None
    assert original.changespecs is not None
    assert len(parsed.changespecs) == len(original.changespecs)
    pc = parsed.changespecs[0]
    oc = original.changespecs[0]
    assert pc.name == oc.name
    assert pc.description == oc.description
    assert pc.status == oc.status
    assert pc.parent == oc.parent
    assert pc.cl == oc.cl
    assert pc.bug == oc.bug
    assert pc.test_targets == oc.test_targets

    # Commits
    assert pc.commits is not None
    assert oc.commits is not None
    assert len(pc.commits) == len(oc.commits)
    assert pc.commits[0].note == oc.commits[0].note

    # Hooks
    assert pc.hooks is not None
    assert oc.hooks is not None
    assert len(pc.hooks) == len(oc.hooks)

    # Comments
    assert pc.comments is not None
    assert oc.comments is not None
    assert len(pc.comments) == len(oc.comments)

    # Mentors
    assert pc.mentors is not None
    assert oc.mentors is not None
    assert len(pc.mentors) == len(oc.mentors)


def test_convert_gp_empty_file(tmp_path: Path) -> None:
    """Empty .gp produces an empty ProjectSpec."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_EMPTY)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.file_path == yaml_path
    assert spec.bug is None
    assert spec.running is None
    assert spec.changespecs is None


def test_convert_gp_validates_against_schema(tmp_path: Path) -> None:
    """Serialized YAML from conversion passes JSON Schema validation."""
    schema_path = Path(__file__).parent.parent / "xprompts" / "project_spec.schema.json"
    with open(schema_path) as f:
        schema = json.load(f)

    gp_path, yaml_path = _write_gp(tmp_path, GP_FULL)
    spec = convert_gp_to_project_spec(gp_path, yaml_path)
    content = serialize_project_spec(spec)
    data = yaml.safe_load(content)

    # Should not raise
    validate(instance=data, schema=schema)


def test_convert_gp_file_path_metadata(tmp_path: Path) -> None:
    """Verify yaml_file_path and line_number=0 set on all ChangeSpecs."""
    gp_path, yaml_path = _write_gp(tmp_path, GP_MULTIPLE_CS)

    spec = convert_gp_to_project_spec(gp_path, yaml_path)

    assert spec.file_path == yaml_path
    assert spec.changespecs is not None
    for cs in spec.changespecs:
        assert cs.file_path == yaml_path
        assert cs.line_number == 0
