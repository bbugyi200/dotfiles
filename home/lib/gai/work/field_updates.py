"""Field update operations for ChangeSpecs (test targets)."""


def _parse_existing_test_targets(lines: list[str], changespec_name: str) -> list[str]:
    """Parse existing TEST TARGETS from a ChangeSpec.

    Args:
        lines: All lines from the project file
        changespec_name: NAME of the ChangeSpec to parse

    Returns:
        List of existing test target strings (with or without FAILED markers)
    """
    existing_targets: list[str] = []
    in_target_changespec = False
    in_test_targets = False

    for line in lines:
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name
            in_test_targets = False
            continue

        if in_target_changespec:
            if line.startswith("TEST TARGETS:"):
                in_test_targets = True
                # Check if targets are on the same line
                targets_inline = line[13:].strip()
                if targets_inline and targets_inline != "None":
                    existing_targets.append(targets_inline)
            elif in_test_targets and line.startswith("  "):
                target = line.strip()
                if target:
                    existing_targets.append(target)
            elif not line.startswith("  "):
                in_test_targets = False

    return existing_targets


def add_failing_test_targets(
    project_file: str, changespec_name: str, new_targets: list[str]
) -> tuple[bool, str | None]:
    """Add failing test targets to a ChangeSpec.

    This function:
    1. Reads existing test targets from the ChangeSpec
    2. For each new target:
       - If already present (with or without FAILED), marks it as FAILED
       - If not present, adds it with (FAILED) marker
    3. Updates the TEST TARGETS field

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_targets: List of test targets to add/mark as failed

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Parse existing test targets
        existing_targets = _parse_existing_test_targets(lines, changespec_name)

        # Build merged target list
        merged_targets: list[str] = []

        # Process existing targets first
        for target in existing_targets:
            # Strip any existing (FAILED) marker for comparison
            base_target = target.replace(" (FAILED)", "")

            if base_target in new_targets:
                # Mark as failed
                merged_targets.append(f"{base_target} (FAILED)")
            else:
                # Keep as-is
                merged_targets.append(target)

        # Add new targets that weren't already in the list
        for new_target in new_targets:
            # Check if this target is already in merged_targets (as base or with FAILED)
            already_present = False
            for merged in merged_targets:
                if merged.replace(" (FAILED)", "") == new_target:
                    already_present = True
                    break

            if not already_present:
                merged_targets.append(f"{new_target} (FAILED)")

        # Format as newline-separated string
        test_targets_str = "\n".join(merged_targets)

        # Use existing update function to write the targets
        return update_test_targets(project_file, changespec_name, test_targets_str)
    except Exception as e:
        return (False, f"Error adding failing test targets: {e}")


def update_test_targets(
    project_file: str, changespec_name: str, test_targets: str
) -> tuple[bool, str | None]:
    """Update the TEST TARGETS field of a specific ChangeSpec in the project file.

    Adds or updates the TEST TARGETS field in a ChangeSpec, inserting it before the STATUS field.
    Supports both single-line format ("//foo:bar //baz:qux") and multi-line format.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        test_targets: Test targets value (space-separated or newline-separated)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Find the ChangeSpec and add/update its TEST TARGETS
        updated_lines = []
        in_target_changespec = False
        current_name = None
        test_targets_updated = False

        # Parse test_targets to determine format
        if "\n" in test_targets:
            # Multi-line format
            targets_list = [t.strip() for t in test_targets.split("\n") if t.strip()]
            test_targets_lines = ["TEST TARGETS:\n"] + [
                f"  {target}\n" for target in targets_list
            ]
        else:
            # Single-line format
            test_targets_lines = [f"TEST TARGETS: {test_targets}\n"]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                i += 1
                continue

            # If we're in the target changespec
            if in_target_changespec:
                # Skip existing TEST TARGETS field if present
                if line.startswith("TEST TARGETS:"):
                    # Skip this line and any following indented lines
                    i += 1
                    while i < len(lines) and lines[i].startswith("  "):
                        i += 1
                    continue

                # Insert TEST TARGETS before STATUS field
                if line.startswith("STATUS:") and not test_targets_updated:
                    updated_lines.extend(test_targets_lines)
                    test_targets_updated = True
                    in_target_changespec = False
                    updated_lines.append(line)
                    i += 1
                    continue

            updated_lines.append(line)
            i += 1

        if not test_targets_updated:
            return (
                False,
                f"Could not find ChangeSpec '{changespec_name}' or STATUS field to insert TEST TARGETS",
            )

        # Write the updated content back to the file
        with open(project_file, "w") as f:
            f.writelines(updated_lines)

        return (True, None)
    except Exception as e:
        return (False, f"Error updating TEST TARGETS: {e}")
