"""Migrate .gp project files to YAML format.

Scans ~/.gai/projects/ for .gp files, converts each to a ProjectSpec YAML
file using the existing parser infrastructure, and optionally removes the
old .gp files.
"""

import argparse
import shutil
import subprocess
from pathlib import Path

from ace.changespec.project_spec import (
    ProjectSpec,
    convert_gp_to_project_spec,
    parse_project_spec,
    serialize_project_spec,
)


def _find_gp_files(project_name: str | None) -> list[Path]:
    """Scan ~/.gai/projects/ for .gp files to migrate.

    Args:
        project_name: If set, only look for this specific project.

    Returns:
        List of Paths to .gp files found.
    """
    projects_dir = Path.home() / ".gai" / "projects"
    if not projects_dir.exists():
        return []

    if project_name:
        gp_file = projects_dir / project_name / f"{project_name}.gp"
        return [gp_file] if gp_file.exists() else []

    gp_files: list[Path] = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        name = project_dir.name
        gp_file = project_dir / f"{name}.gp"
        if gp_file.exists():
            gp_files.append(gp_file)
    return gp_files


def _verify_round_trip(original_spec: ProjectSpec, yaml_file: str) -> list[str]:
    """Parse the written YAML back and compare with the original spec.

    Args:
        original_spec: The ProjectSpec that was serialized and written.
        yaml_file: Path to the written YAML file.

    Returns:
        List of error messages (empty if verification passed).
    """
    errors: list[str] = []
    try:
        parsed = parse_project_spec(yaml_file)
    except Exception as e:
        return [f"Failed to parse {yaml_file}: {e}"]

    if parsed.bug != original_spec.bug:
        errors.append(f"bug mismatch: {parsed.bug!r} != {original_spec.bug!r}")

    orig_cs = original_spec.changespecs or []
    parsed_cs = parsed.changespecs or []
    if len(parsed_cs) != len(orig_cs):
        errors.append(f"changespec count: {len(parsed_cs)} != {len(orig_cs)}")
    else:
        for i, (pc, oc) in enumerate(zip(parsed_cs, orig_cs, strict=True)):
            if pc.name != oc.name:
                errors.append(f"changespecs[{i}].name: {pc.name!r} != {oc.name!r}")
            if pc.status != oc.status:
                errors.append(
                    f"changespecs[{i}].status: {pc.status!r} != {oc.status!r}"
                )

    orig_run = original_spec.running or []
    parsed_run = parsed.running or []
    if len(parsed_run) != len(orig_run):
        errors.append(f"running count: {len(parsed_run)} != {len(orig_run)}")

    return errors


def _migrate_single_project(gp_file: Path, dry_run: bool, remove_old: bool) -> bool:
    """Convert a single .gp file to .yaml.

    Args:
        gp_file: Path to the .gp file.
        dry_run: If True, only print what would happen.
        remove_old: If True, delete the .gp file after successful migration.

    Returns:
        True if migration succeeded (or would succeed in dry-run), False on error.
    """
    yaml_file = gp_file.with_suffix(".yaml")
    project_name = gp_file.stem

    if yaml_file.exists():
        print(f"  SKIP {project_name}: {yaml_file.name} already exists")
        return False

    try:
        spec = convert_gp_to_project_spec(str(gp_file), str(yaml_file))
    except Exception as e:
        print(f"  FAIL {project_name}: conversion error: {e}")
        return False

    content = serialize_project_spec(spec)

    if dry_run:
        cs_count = len(spec.changespecs) if spec.changespecs else 0
        run_count = len(spec.running) if spec.running else 0
        print(
            f"  {project_name}: {cs_count} changespec(s), {run_count} running claim(s)"
        )
        return True

    # Write the YAML file
    yaml_file.write_text(content)

    # Round-trip verification
    errors = _verify_round_trip(spec, str(yaml_file))
    if errors:
        print(f"  FAIL {project_name}: round-trip verification errors:")
        for err in errors:
            print(f"    - {err}")
        # Remove the broken YAML to avoid leaving partial state
        yaml_file.unlink(missing_ok=True)
        return False

    print(f"  OK   {project_name}: {gp_file.name} -> {yaml_file.name}")

    # Format the YAML file if yamlfmt is available
    if shutil.which("yamlfmt"):
        try:
            subprocess.run(["yamlfmt", str(yaml_file)], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"  WARN {project_name}: yamlfmt failed: {e}")

    if remove_old:
        gp_file.unlink()
        print(f"       removed {gp_file.name}")

    return True


def _git_commit_all(migrated_files: list[Path], removed_files: list[Path]) -> None:
    """Stage and commit all migration changes in ~/.gai.

    Args:
        migrated_files: Newly created .yaml files.
        removed_files: Deleted .gp files.
    """
    gai_dir = Path.home() / ".gai"

    for f in migrated_files:
        subprocess.run(
            ["git", "add", str(f)],
            cwd=str(gai_dir),
            check=True,
            capture_output=True,
        )
    for f in removed_files:
        subprocess.run(
            ["git", "rm", "--cached", str(f)],
            cwd=str(gai_dir),
            check=False,
            capture_output=True,
        )

    count = len(migrated_files)
    msg = f"Migrate {count} project(s) from .gp to .yaml"
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(gai_dir),
        check=True,
        capture_output=True,
    )
    print(f"\nCommitted: {msg}")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate .gp project files to YAML format."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing any files.",
    )
    parser.add_argument(
        "--remove-old",
        action="store_true",
        help="Delete .gp files after successful migration.",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Only migrate a specific project by name.",
    )
    return parser.parse_args()


def main() -> None:
    """Orchestrate the .gp-to-YAML migration."""
    args = _parse_args()

    gp_files = _find_gp_files(args.project)
    if not gp_files:
        print("Nothing to migrate.")
        return

    mode = " (dry run)" if args.dry_run else ""
    print(f"Migrating {len(gp_files)} project(s){mode}:\n")

    migrated: list[Path] = []
    removed: list[Path] = []
    failed = 0

    for gp_file in gp_files:
        ok = _migrate_single_project(gp_file, args.dry_run, args.remove_old)
        if ok and not args.dry_run:
            migrated.append(gp_file.with_suffix(".yaml"))
            if args.remove_old:
                removed.append(gp_file)
        elif not ok:
            failed += 1

    # Summary
    print(f"\nDone: {len(migrated)} migrated, {failed} failed.")

    # Git commit (only when we actually wrote files)
    if migrated and not args.dry_run:
        try:
            _git_commit_all(migrated, removed)
        except subprocess.CalledProcessError as e:
            print(f"Warning: git commit failed: {e}")


if __name__ == "__main__":
    main()
