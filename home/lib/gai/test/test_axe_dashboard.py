"""Tests for the axe dashboard widget utility functions."""

from ace.tui.widgets.axe_dashboard import AxeDashboard, _format_runtime, _format_uptime


def test_format_uptime_seconds_only() -> None:
    """Test formatting uptime with only seconds."""
    assert _format_uptime(30) == "30s"


def test_format_uptime_minutes_and_seconds() -> None:
    """Test formatting uptime with minutes and seconds."""
    assert _format_uptime(90) == "1m 30s"


def test_format_uptime_hours_minutes_seconds() -> None:
    """Test formatting uptime with hours, minutes, and seconds."""
    assert _format_uptime(3723) == "1h 2m 3s"


def test_format_uptime_zero() -> None:
    """Test formatting uptime with zero seconds."""
    assert _format_uptime(0) == "0s"


def test_format_uptime_exact_hour() -> None:
    """Test formatting uptime for exactly 1 hour."""
    assert _format_uptime(3600) == "1h 0m 0s"


def test_format_uptime_exact_minute() -> None:
    """Test formatting uptime for exactly 1 minute."""
    assert _format_uptime(60) == "1m 0s"


def test_format_uptime_large() -> None:
    """Test formatting uptime with many hours."""
    # 50 hours, 30 minutes, 15 seconds
    assert _format_uptime(181815) == "50h 30m 15s"


def test_format_runtime_invalid() -> None:
    """Test formatting runtime with invalid timestamp."""
    assert _format_runtime("invalid") == "unknown"


def test_format_runtime_empty() -> None:
    """Test formatting runtime with empty string."""
    assert _format_runtime("") == "unknown"


def test_format_runtime_none_type() -> None:
    """Test formatting runtime with None-like value."""
    # Passing an empty dict or list as string would fail parsing
    assert _format_runtime("{}") == "unknown"
    assert _format_runtime("[]") == "unknown"


def test_axe_dashboard_init() -> None:
    """Test AxeDashboard initialization."""
    dashboard = AxeDashboard()
    # Check that it can be instantiated without error
    assert dashboard is not None
