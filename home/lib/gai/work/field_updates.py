"""Field update operations for ChangeSpecs (TAP and test targets)."""

import re


def _extract_cl_number(cl_value: str) -> str | None:
    """Extract CL number from a CL field value.

    The CL field can be:
    - A URL like "http://cl/829085633"
    - A number like "829085633"

    Args:
        cl_value: The CL field value from a ChangeSpec

    Returns:
        The CL number as a string if found, None otherwise
    """
    if not cl_value or cl_value == "None":
        return None

    # Try to extract from URL pattern first (e.g., "http://cl/829085633")
    url_match = re.search(r"(?:https?://)?cl/(\d+)", cl_value)
    if url_match:
        return url_match.group(1)

    # If it's just a number string
    if cl_value.isdigit():
        return cl_value

    return None


def _construct_tap_url(cl_number: str) -> str:
    """Construct TAP URL from a CL number.

    Args:
        cl_number: The CL number (e.g., "829085633")

    Returns:
        The TAP URL (e.g., "http://fusion2/presubmit?q=cl:829085633")
    """
    return f"http://fusion2/presubmit?q=cl:{cl_number}"


def _update_tap_field(
    project_file: str, changespec_name: str, tap_url: str
) -> tuple[bool, str | None]:
    """Update the TAP field of a specific ChangeSpec in the project file.

    Adds or updates the TAP field in a ChangeSpec, inserting it before the STATUS field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        tap_url: TAP URL to set (e.g., "https://tap.example.com/12345")

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Find the ChangeSpec and add/update its TAP field
        updated_lines = []
        in_target_changespec = False
        current_name = None
        tap_updated = False

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
                # Skip existing TAP field if present
                if line.startswith("TAP:"):
                    i += 1
                    continue

                # Insert TAP before STATUS field
                if line.startswith("STATUS:") and not tap_updated:
                    updated_lines.append(f"TAP: {tap_url}\n")
                    tap_updated = True
                    in_target_changespec = False
                    updated_lines.append(line)
                    i += 1
                    continue

            updated_lines.append(line)
            i += 1

        if not tap_updated:
            return (
                False,
                f"Could not find ChangeSpec '{changespec_name}' or STATUS field to insert TAP",
            )

        # Write the updated content back to the file
        with open(project_file, "w") as f:
            f.writelines(updated_lines)

        return (True, None)
    except Exception as e:
        return (False, f"Error updating TAP field: {e}")


def update_tap_field_from_cl(
    project_file: str, changespec_name: str
) -> tuple[bool, str | None]:
    """Update the TAP field by constructing the URL from the CL field.

    Reads the CL field from the specified ChangeSpec, extracts the CL number,
    constructs the TAP URL using the pattern http://fusion2/presubmit?q=cl:<CL>,
    and updates the TAP field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with open(project_file) as f:
            lines = f.readlines()

        # Find the ChangeSpec and extract the CL field
        in_target_changespec = False
        current_name = None
        cl_value = None

        for line in lines:
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                continue

            # If we're in the target changespec, look for CL field
            if in_target_changespec:
                if line.startswith("CL:"):
                    cl_value = line.split(":", 1)[1].strip()
                    break
                # Stop if we hit STATUS (CL should come before STATUS)
                if line.startswith("STATUS:"):
                    break

        if not in_target_changespec:
            return (False, f"Could not find ChangeSpec '{changespec_name}'")

        if not cl_value or cl_value == "None":
            return (False, f"ChangeSpec '{changespec_name}' has no CL field set")

        # Extract CL number and construct TAP URL
        cl_number = _extract_cl_number(cl_value)
        if not cl_number:
            return (False, f"Could not extract CL number from CL value: {cl_value}")

        tap_url = _construct_tap_url(cl_number)

        # Update the TAP field using existing function
        return _update_tap_field(project_file, changespec_name, tap_url)

    except Exception as e:
        return (False, f"Error updating TAP field from CL: {e}")


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
