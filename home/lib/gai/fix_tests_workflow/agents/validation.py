import os

from ..state import (
    FixTestsState,
    extract_file_modifications_from_response,
    get_latest_planner_response,
)


def _parse_file_bullets_from_todos(todos_content: str) -> list[tuple[str, bool]]:
    """
    Parse + bullets from content to extract file paths and their NEW status.

    Returns:
        List of tuples: (file_path, is_new_file)
    """
    file_bullets: list[tuple[str, bool]] = []
    if not todos_content:
        return file_bullets
    lines = todos_content.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("+ "):
            bullet_content = stripped[2:].strip()
            if bullet_content.startswith("NEW "):
                file_path = bullet_content[4:].strip()
                if file_path.startswith("google3/"):
                    file_path = file_path[8:]
                if file_path:
                    file_bullets.append((file_path, True))
            elif bullet_content.startswith("@"):
                file_path = bullet_content[1:].strip()
                if file_path.startswith("google3/"):
                    file_path = file_path[8:]
                if file_path:
                    file_bullets.append((file_path, False))
    return file_bullets


def validate_file_paths(state: FixTestsState) -> FixTestsState:
    """
    Validate that file paths in + bullets match reality before running verification agent.

    This checks:
    - Files marked with @path (existing) actually exist
    - Files marked with NEW path (new) do NOT already exist
    """
    print("Validating file paths from planner response...")
    planner_response = get_latest_planner_response(state)
    if not planner_response:
        print("⚠️ Warning: No planner response found - skipping file path validation")
        return state
    try:
        file_modifications = extract_file_modifications_from_response(planner_response)
        if not file_modifications:
            print(
                "⚠️ Warning: No file modifications found in planner response - skipping file path validation"
            )
            return state
        file_bullets = _parse_file_bullets_from_todos(file_modifications)
        if not file_bullets:
            print("📄 No file bullets found in planner response")
            return state
        validation_errors = []
        for file_path, is_new_file in file_bullets:
            file_exists = os.path.exists(file_path)
            if is_new_file and file_exists:
                validation_errors.append(
                    f"File marked as NEW already exists: {file_path}"
                )
                print(f"❌ Validation error: NEW file already exists: {file_path}")
            elif not is_new_file and (not file_exists):
                validation_errors.append(
                    f"File marked as existing does not exist: {file_path}"
                )
                print(f"❌ Validation error: Existing file not found: {file_path}")
            else:
                status = "NEW (non-existent)" if is_new_file else "existing"
                print(f"✅ File path valid: {file_path} ({status})")
        if validation_errors:
            updated_verifier_notes = state.get("verifier_notes", []).copy()
            error_note = f"File path validation failed: {'; '.join(validation_errors)}. Please ensure files marked with @ actually exist, and files marked as NEW do not already exist."
            updated_verifier_notes.append(error_note)
            print(
                f"📝 Added file path validation error to verifier notes: {error_note}"
            )
            return {
                **state,
                "verification_passed": False,
                "needs_editor_retry": True,
                "verifier_notes": updated_verifier_notes,
            }
        else:
            print(f"✅ All {len(file_bullets)} file paths validated successfully")
            return state
    except Exception as e:
        print(f"⚠️ Warning: Error during file path validation: {e}")
        return state
