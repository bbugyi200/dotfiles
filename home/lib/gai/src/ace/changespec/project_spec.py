"""ProjectSpec and WorkspaceClaim data models, YAML parse/serialize/write."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from jsonschema import validate  # type: ignore[import-untyped]
from shared_utils import dump_yaml

from .locking import changespec_lock, write_changespec_atomic
from .models import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
)


@dataclass
class WorkspaceClaim:
    """Workspace claim in the RUNNING field."""

    workspace_num: int
    pid: int
    workflow: str
    cl_name: str | None = None
    artifacts_timestamp: str | None = None


@dataclass
class ProjectSpec:
    """Complete project specification file wrapper."""

    file_path: str
    bug: str | None = None
    running: list[WorkspaceClaim] | None = None
    changespecs: list[ChangeSpec] | None = None


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


@cache
def _load_schema() -> dict[str, Any]:
    """Load the project_spec JSON schema."""
    schema_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "xprompts"
        / "project_spec.schema.json"
    )
    with open(schema_path) as f:
        return json.load(f)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Dict ↔ dataclass helpers
# ---------------------------------------------------------------------------


def _remove_none_values(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove None values from a dict."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        if value is None:
            continue
        if isinstance(value, dict):
            result[key] = _remove_none_values(value)
        elif isinstance(value, list):
            result[key] = [
                _remove_none_values(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _project_spec_to_dict(spec: ProjectSpec) -> dict[str, Any]:
    """Convert a ProjectSpec to a dict suitable for YAML serialization.

    Excludes metadata fields (file_path, line_number) and omits None values.
    """
    d = asdict(spec)
    # Remove metadata from ProjectSpec
    d.pop("file_path", None)
    # Remove metadata from each ChangeSpec
    if d.get("changespecs") is not None:
        for cs in d["changespecs"]:
            cs.pop("file_path", None)
            cs.pop("line_number", None)
    return _remove_none_values(d)


def _build_hook_entry(hook_data: dict[str, Any]) -> HookEntry:
    """Build a HookEntry from a parsed YAML dict."""
    status_lines = None
    raw_lines = hook_data.get("status_lines")
    if raw_lines is not None:
        status_lines = [HookStatusLine(**sl) for sl in raw_lines]
    return HookEntry(command=hook_data["command"], status_lines=status_lines)


def _build_mentor_entry(mentor_data: dict[str, Any]) -> MentorEntry:
    """Build a MentorEntry from a parsed YAML dict."""
    status_lines = None
    raw_lines = mentor_data.get("status_lines")
    if raw_lines is not None:
        status_lines = [MentorStatusLine(**sl) for sl in raw_lines]
    return MentorEntry(
        entry_id=mentor_data["entry_id"],
        profiles=mentor_data["profiles"],
        status_lines=status_lines,
        is_wip=mentor_data.get("is_wip", False),
    )


def _build_changespec(cs_data: dict[str, Any], file_path: str) -> ChangeSpec:
    """Build a ChangeSpec from a parsed YAML dict."""
    commits = None
    raw_commits = cs_data.get("commits")
    if raw_commits is not None:
        commits = [CommitEntry(**ce) for ce in raw_commits]

    hooks = None
    raw_hooks = cs_data.get("hooks")
    if raw_hooks is not None:
        hooks = [_build_hook_entry(h) for h in raw_hooks]

    comments = None
    raw_comments = cs_data.get("comments")
    if raw_comments is not None:
        comments = [CommentEntry(**ce) for ce in raw_comments]

    mentors = None
    raw_mentors = cs_data.get("mentors")
    if raw_mentors is not None:
        mentors = [_build_mentor_entry(m) for m in raw_mentors]

    return ChangeSpec(
        name=cs_data["name"],
        description=cs_data["description"],
        parent=cs_data.get("parent"),
        cl=cs_data.get("cl"),
        status=cs_data["status"],
        test_targets=cs_data.get("test_targets"),
        kickstart=cs_data.get("kickstart"),
        file_path=file_path,
        line_number=0,
        bug=cs_data.get("bug"),
        commits=commits,
        hooks=hooks,
        comments=comments,
        mentors=mentors,
    )


def _dict_to_project_spec(data: dict[str, Any], file_path: str) -> ProjectSpec:
    """Convert a parsed YAML dict to a ProjectSpec dataclass tree."""
    running = None
    raw_running = data.get("running")
    if raw_running is not None:
        running = [WorkspaceClaim(**claim) for claim in raw_running]

    changespecs = None
    raw_changespecs = data.get("changespecs")
    if raw_changespecs is not None:
        changespecs = [_build_changespec(cs, file_path) for cs in raw_changespecs]

    return ProjectSpec(
        file_path=file_path,
        bug=data.get("bug"),
        running=running,
        changespecs=changespecs,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def serialize_project_spec(spec: ProjectSpec) -> str:
    """Serialize a ProjectSpec to a YAML string."""
    d = _project_spec_to_dict(spec)
    return dump_yaml(d, sort_keys=False)


def parse_project_spec(file_path: str) -> ProjectSpec:
    """Parse a YAML project spec file into a ProjectSpec.

    Validates the file contents against the JSON schema before conversion.
    Returns an empty ProjectSpec for empty files.
    """
    with open(file_path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return ProjectSpec(file_path=file_path)
    schema = _load_schema()
    validate(instance=data, schema=schema)
    return _dict_to_project_spec(data, file_path)


def write_project_spec_atomic(
    project_file: str,
    spec: ProjectSpec,
    commit_message: str,
) -> None:
    """Write a ProjectSpec to a YAML file atomically and commit to git."""
    content = serialize_project_spec(spec)
    write_changespec_atomic(project_file, content, commit_message)


@contextmanager
def read_and_update_project_spec(
    project_file: str,
    commit_message: str,
) -> Iterator[ProjectSpec]:
    """Read a project spec, yield for mutation, then write back atomically.

    Acquires a lock on the file, parses it, yields the ProjectSpec for the
    caller to mutate, and writes the modified spec back on exit.
    """
    with changespec_lock(project_file):
        spec = parse_project_spec(project_file)
        yield spec
        write_project_spec_atomic(project_file, spec, commit_message)
