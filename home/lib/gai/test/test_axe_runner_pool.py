"""Tests for the axe runner pool module."""

from unittest.mock import patch

from axe.runner_pool import RunnerPool


def test_runner_pool_init_default_max_runners() -> None:
    """Test RunnerPool initializes with default max_runners."""
    pool = RunnerPool()
    assert pool.max_runners == 5


def test_runner_pool_init_custom_max_runners() -> None:
    """Test RunnerPool initializes with custom max_runners."""
    pool = RunnerPool(max_runners=10)
    assert pool.max_runners == 10


def test_reset_tick_clears_started_count() -> None:
    """Test that reset_tick clears the started count."""
    pool = RunnerPool(max_runners=5)

    # Simulate some runners being started
    pool._started_this_tick = 3

    pool.reset_tick()
    assert pool.get_started_this_tick() == 0


def test_get_started_this_tick_returns_count() -> None:
    """Test that get_started_this_tick returns the current count."""
    pool = RunnerPool(max_runners=5)
    assert pool.get_started_this_tick() == 0

    pool._started_this_tick = 2
    assert pool.get_started_this_tick() == 2


@patch("axe.runner_pool.count_all_runners_global")
def test_get_current_runners_includes_global(mock_count: object) -> None:
    """Test that get_current_runners includes global count."""
    mock_count.return_value = 3  # type: ignore
    pool = RunnerPool(max_runners=10)
    pool._started_this_tick = 2

    # Should be global (3) + this_tick (2) = 5
    assert pool.get_current_runners() == 5


@patch("axe.runner_pool.count_all_runners_global")
def test_get_available_slots_calculates_correctly(mock_count: object) -> None:
    """Test that get_available_slots calculates available slots."""
    mock_count.return_value = 2  # type: ignore
    pool = RunnerPool(max_runners=5)
    pool._started_this_tick = 1

    # max (5) - global (2) - this_tick (1) = 2 available
    assert pool.get_available_slots() == 2


@patch("axe.runner_pool.count_all_runners_global")
def test_get_available_slots_returns_zero_when_at_limit(mock_count: object) -> None:
    """Test that get_available_slots returns 0 when at limit."""
    mock_count.return_value = 4  # type: ignore
    pool = RunnerPool(max_runners=5)
    pool._started_this_tick = 1

    # max (5) - global (4) - this_tick (1) = 0 available
    assert pool.get_available_slots() == 0


@patch("axe.runner_pool.count_all_runners_global")
def test_get_available_slots_never_negative(mock_count: object) -> None:
    """Test that get_available_slots never returns negative."""
    mock_count.return_value = 10  # type: ignore  # More than max
    pool = RunnerPool(max_runners=5)

    # Should be 0, not negative
    assert pool.get_available_slots() == 0


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slot_success(mock_count: object) -> None:
    """Test that reserve_slot succeeds when slots available."""
    mock_count.return_value = 2  # type: ignore
    pool = RunnerPool(max_runners=5)

    # Should succeed - 2 global, max 5, so 3 available
    assert pool.reserve_slot() is True
    assert pool.get_started_this_tick() == 1


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slot_fails_at_limit(mock_count: object) -> None:
    """Test that reserve_slot fails when at limit."""
    mock_count.return_value = 5  # type: ignore
    pool = RunnerPool(max_runners=5)

    # Should fail - already at max
    assert pool.reserve_slot() is False
    assert pool.get_started_this_tick() == 0


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slot_multiple_times(mock_count: object) -> None:
    """Test reserving slots multiple times."""
    mock_count.return_value = 0  # type: ignore
    pool = RunnerPool(max_runners=3)

    # Reserve all 3 slots
    assert pool.reserve_slot() is True
    assert pool.reserve_slot() is True
    assert pool.reserve_slot() is True

    # 4th should fail
    assert pool.reserve_slot() is False
    assert pool.get_started_this_tick() == 3


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slots_reserves_requested_count(mock_count: object) -> None:
    """Test that reserve_slots reserves the requested count."""
    mock_count.return_value = 0  # type: ignore
    pool = RunnerPool(max_runners=10)

    reserved = pool.reserve_slots(5)
    assert reserved == 5
    assert pool.get_started_this_tick() == 5


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slots_reserves_only_available(mock_count: object) -> None:
    """Test that reserve_slots reserves only available slots."""
    mock_count.return_value = 3  # type: ignore
    pool = RunnerPool(max_runners=5)

    # Request 10 but only 2 available (5 - 3)
    reserved = pool.reserve_slots(10)
    assert reserved == 2
    assert pool.get_started_this_tick() == 2


@patch("axe.runner_pool.count_all_runners_global")
def test_reserve_slots_returns_zero_when_none_available(mock_count: object) -> None:
    """Test that reserve_slots returns 0 when none available."""
    mock_count.return_value = 5  # type: ignore
    pool = RunnerPool(max_runners=5)

    reserved = pool.reserve_slots(3)
    assert reserved == 0
    assert pool.get_started_this_tick() == 0


@patch("axe.runner_pool.count_all_runners_global")
def test_add_started_increments_count(mock_count: object) -> None:
    """Test that add_started increments the started count."""
    mock_count.return_value = 0  # type: ignore
    pool = RunnerPool(max_runners=10)

    pool.add_started(3)
    assert pool.get_started_this_tick() == 3

    pool.add_started(2)
    assert pool.get_started_this_tick() == 5


@patch("axe.runner_pool.count_all_runners_global")
def test_is_at_limit_true_when_at_max(mock_count: object) -> None:
    """Test that is_at_limit returns True when at max."""
    mock_count.return_value = 5  # type: ignore
    pool = RunnerPool(max_runners=5)

    assert pool.is_at_limit() is True


@patch("axe.runner_pool.count_all_runners_global")
def test_is_at_limit_false_when_slots_available(mock_count: object) -> None:
    """Test that is_at_limit returns False when slots available."""
    mock_count.return_value = 2  # type: ignore
    pool = RunnerPool(max_runners=5)

    assert pool.is_at_limit() is False


@patch("axe.runner_pool.count_all_runners_global")
def test_reset_tick_and_reserve_workflow(mock_count: object) -> None:
    """Test the typical workflow of reset_tick followed by reserves."""
    mock_count.return_value = 0  # type: ignore
    pool = RunnerPool(max_runners=3)

    # Simulate first tick
    assert pool.reserve_slot() is True
    assert pool.reserve_slot() is True
    assert pool.get_started_this_tick() == 2

    # Reset for next tick
    pool.reset_tick()
    assert pool.get_started_this_tick() == 0

    # Can reserve again
    assert pool.reserve_slot() is True
    assert pool.get_started_this_tick() == 1


@patch("axe.runner_pool.count_all_runners_global")
def test_thread_safety_basic(mock_count: object) -> None:
    """Test that basic operations don't fail with the lock."""
    mock_count.return_value = 0  # type: ignore
    pool = RunnerPool(max_runners=10)

    # These should all work without deadlock
    pool.reset_tick()
    pool.get_started_this_tick()
    pool.get_current_runners()
    pool.get_available_slots()
    pool.reserve_slot()
    pool.reserve_slots(2)
    pool.add_started(1)
    pool.is_at_limit()
