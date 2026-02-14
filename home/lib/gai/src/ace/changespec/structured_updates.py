"""Immutable update functions for ProjectSpec and ChangeSpec.

All functions return new instances via dataclasses.replace() and never mutate inputs.
"""

from dataclasses import replace

from .models import ChangeSpec, CommentEntry, CommitEntry, HookEntry, MentorEntry
from .project_spec import ProjectSpec, WorkspaceClaim


def _find_changespec(spec: ProjectSpec, cs_name: str) -> tuple[int, ChangeSpec]:
    """Locate a ChangeSpec by name within a ProjectSpec.

    Args:
        spec: The ProjectSpec to search.
        cs_name: The ChangeSpec name to find.

    Returns:
        Tuple of (index, ChangeSpec).

    Raises:
        ValueError: If cs_name is not found or changespecs is None/empty.
    """
    if not spec.changespecs:
        available = "(none)"
        raise ValueError(f"ChangeSpec {cs_name!r} not found. Available: {available}")
    for i, cs in enumerate(spec.changespecs):
        if cs.name == cs_name:
            return i, cs
    available = ", ".join(cs.name for cs in spec.changespecs)
    raise ValueError(f"ChangeSpec {cs_name!r} not found. Available: {available}")


def _replace_changespec(
    spec: ProjectSpec, index: int, new_cs: ChangeSpec
) -> ProjectSpec:
    """Return a new ProjectSpec with the ChangeSpec at index replaced.

    Args:
        spec: The original ProjectSpec.
        index: Index of the ChangeSpec to replace.
        new_cs: The new ChangeSpec to insert.

    Returns:
        A new ProjectSpec with the updated changespecs list.
    """
    assert spec.changespecs is not None
    new_list = list(spec.changespecs)
    new_list[index] = new_cs
    return replace(spec, changespecs=new_list)


def update_changespec_status(
    spec: ProjectSpec, cs_name: str, new_status: str
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's status updated."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, status=new_status))


def update_changespec_cl(
    spec: ProjectSpec, cs_name: str, new_cl: str | None
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's cl updated."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, cl=new_cl))


def update_changespec_parent(
    spec: ProjectSpec, cs_name: str, new_parent: str | None
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's parent updated."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, parent=new_parent))


def update_changespec_description(
    spec: ProjectSpec, cs_name: str, new_description: str
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's description updated."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, description=new_description))


def update_changespec_hooks(
    spec: ProjectSpec, cs_name: str, hooks: list[HookEntry] | None
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's hooks replaced."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, hooks=hooks))


def update_changespec_comments(
    spec: ProjectSpec, cs_name: str, comments: list[CommentEntry] | None
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's comments replaced."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, comments=comments))


def update_changespec_mentors(
    spec: ProjectSpec, cs_name: str, mentors: list[MentorEntry] | None
) -> ProjectSpec:
    """Return a new ProjectSpec with the named ChangeSpec's mentors replaced."""
    idx, cs = _find_changespec(spec, cs_name)
    return _replace_changespec(spec, idx, replace(cs, mentors=mentors))


def add_changespec_commit_entry(
    spec: ProjectSpec, cs_name: str, entry: CommitEntry
) -> ProjectSpec:
    """Return a new ProjectSpec with a CommitEntry appended to the named ChangeSpec.

    Initializes the commits list from None if needed.
    """
    idx, cs = _find_changespec(spec, cs_name)
    existing = list(cs.commits) if cs.commits else []
    existing.append(entry)
    return _replace_changespec(spec, idx, replace(cs, commits=existing))


def update_commit_entry_suffix(
    spec: ProjectSpec,
    cs_name: str,
    entry_id: str,
    suffix: str | None,
    suffix_type: str | None,
) -> ProjectSpec:
    """Return a new ProjectSpec with the suffix updated on a specific CommitEntry.

    Matches by CommitEntry.display_number (e.g. "1", "1a").

    Raises:
        ValueError: If the ChangeSpec has no commits or the entry_id is not found.
    """
    idx, cs = _find_changespec(spec, cs_name)
    if not cs.commits:
        raise ValueError(f"ChangeSpec {cs_name!r} has no commits")
    new_commits: list[CommitEntry] = []
    found = False
    for commit in cs.commits:
        if commit.display_number == entry_id:
            new_commits.append(replace(commit, suffix=suffix, suffix_type=suffix_type))
            found = True
        else:
            new_commits.append(commit)
    if not found:
        available = ", ".join(c.display_number for c in cs.commits)
        raise ValueError(
            f"CommitEntry {entry_id!r} not found in {cs_name!r}. Available: {available}"
        )
    return _replace_changespec(spec, idx, replace(cs, commits=new_commits))


def add_running_claim(spec: ProjectSpec, claim: WorkspaceClaim) -> ProjectSpec:
    """Return a new ProjectSpec with a WorkspaceClaim appended to running.

    Initializes the running list from None if needed.
    """
    existing = list(spec.running) if spec.running else []
    existing.append(claim)
    return replace(spec, running=existing)


def remove_running_claim(
    spec: ProjectSpec,
    workspace_num: int,
    workflow: str | None = None,
) -> ProjectSpec:
    """Return a new ProjectSpec with matching WorkspaceClaim(s) removed from running.

    Matches by workspace_num. If workflow is provided, also filters by workflow.
    Sets running to None when the list becomes empty.
    Returns unchanged spec if no match is found or running is None.
    """
    if not spec.running:
        return spec
    filtered = [
        c
        for c in spec.running
        if not (
            c.workspace_num == workspace_num
            and (workflow is None or c.workflow == workflow)
        )
    ]
    if len(filtered) == len(spec.running):
        return spec
    return replace(spec, running=filtered or None)


def update_parent_references(
    spec: ProjectSpec, old_name: str, new_name: str
) -> ProjectSpec:
    """Return a new ProjectSpec with parent references renamed across all ChangeSpecs.

    Any ChangeSpec whose parent matches old_name gets updated to new_name.
    Returns unchanged spec if no matches are found or changespecs is None.
    """
    if not spec.changespecs:
        return spec
    new_list: list[ChangeSpec] = []
    changed = False
    for cs in spec.changespecs:
        if cs.parent == old_name:
            new_list.append(replace(cs, parent=new_name))
            changed = True
        else:
            new_list.append(cs)
    if not changed:
        return spec
    return replace(spec, changespecs=new_list)
