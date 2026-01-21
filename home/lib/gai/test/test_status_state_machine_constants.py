"""Tests for status_state_machine validation and transition checks."""

from status_state_machine import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    is_valid_transition,
    remove_workspace_suffix,
)


def test_valid_statuses_defined() -> None:
    """Test that all valid statuses are defined."""
    expected_statuses = [
        "WIP",
        "Drafted",
        "Mailed",
        "Submitted",
        "Reverted",
    ]
    assert VALID_STATUSES == expected_statuses


def test_valid_transitions_defined() -> None:
    """Test that valid transitions are defined for all statuses."""
    # Ensure all valid statuses have an entry in transitions
    for status in VALID_STATUSES:
        assert status in VALID_TRANSITIONS


def test_is_valid_transition_wip_to_drafted() -> None:
    """Test transition from 'WIP' to 'Drafted' is valid."""
    assert is_valid_transition("WIP", "Drafted") is True


def test_is_valid_transition_invalid_from_wip() -> None:
    """Test that WIP can only transition to Drafted."""
    assert is_valid_transition("WIP", "Mailed") is False
    assert is_valid_transition("WIP", "Submitted") is False
    assert is_valid_transition("WIP", "Reverted") is False


def test_is_valid_transition_drafted_to_mailed() -> None:
    """Test transition from 'Drafted' to 'Mailed' is valid."""
    assert is_valid_transition("Drafted", "Mailed") is True


def test_is_valid_transition_mailed_to_submitted() -> None:
    """Test transition from 'Mailed' to 'Submitted' is valid."""
    assert is_valid_transition("Mailed", "Submitted") is True


def test_is_valid_transition_invalid_from_submitted() -> None:
    """Test that transitions from 'Submitted' (terminal state) are invalid."""
    assert is_valid_transition("Submitted", "Mailed") is False
    assert is_valid_transition("Submitted", "Drafted") is False


def test_is_valid_transition_invalid_from_reverted() -> None:
    """Test that transitions from 'Reverted' (terminal state) are invalid."""
    assert is_valid_transition("Reverted", "Mailed") is False
    assert is_valid_transition("Reverted", "Drafted") is False


def test_is_valid_transition_invalid_status() -> None:
    """Test that invalid status names are rejected."""
    assert is_valid_transition("Invalid Status", "Mailed") is False
    assert is_valid_transition("Mailed", "Invalid Status") is False


def test_remove_workspace_suffix_with_workspace() -> None:
    """Test remove_workspace_suffix strips workspace suffix."""
    assert remove_workspace_suffix("WIP (fig_3)") == "WIP"
    assert remove_workspace_suffix("Drafted (project_99)") == "Drafted"
    assert remove_workspace_suffix("Mailed (my-proj_1)") == "Mailed"


def test_remove_workspace_suffix_no_suffix() -> None:
    """Test remove_workspace_suffix returns unchanged when no suffix."""
    assert remove_workspace_suffix("WIP") == "WIP"
    assert remove_workspace_suffix("Drafted") == "Drafted"
    assert remove_workspace_suffix("Mailed") == "Mailed"
    assert remove_workspace_suffix("Submitted") == "Submitted"


def test_remove_workspace_suffix_both_suffixes() -> None:
    """Test remove_workspace_suffix removes both workspace and READY TO MAIL."""
    # Note: This pattern shouldn't occur in practice but tests the function
    result = remove_workspace_suffix("Drafted - (!: READY TO MAIL)")
    assert result == "Drafted"


def test_is_valid_transition_with_workspace_suffix() -> None:
    """Test that is_valid_transition handles workspace suffixes correctly."""
    assert is_valid_transition("WIP (fig_3)", "Drafted") is True
    assert is_valid_transition("Drafted", "Mailed (project_1)") is True
    assert is_valid_transition("WIP (proj_1)", "Drafted (proj_2)") is True


def test_is_valid_transition_drafted_to_wip() -> None:
    """Test that Drafted CAN transition back to WIP."""
    assert is_valid_transition("Drafted", "WIP") is True


def test_is_valid_transition_mailed_cannot_go_back() -> None:
    """Test that Mailed cannot transition back to Drafted or WIP."""
    assert is_valid_transition("Mailed", "Drafted") is False
    assert is_valid_transition("Mailed", "WIP") is False
