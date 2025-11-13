"""Field update operations for ChangeSpecs (test targets)."""


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
