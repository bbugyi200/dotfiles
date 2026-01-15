"""Concurrency management for gai axe scheduler.

This module provides a runner pool that enforces the max_runners limit
across all scheduled jobs within a single tick of the scheduler.
"""

from threading import Lock

from ace.changespec import count_all_runners_global


class RunnerPool:
    """Thread-safe runner pool for concurrency management.

    Tracks runners started within the current scheduler tick and enforces
    the max_runners limit when combined with globally running processes.

    The pool is reset at the start of each scheduler tick via reset_tick().
    """

    def __init__(self, max_runners: int = 5) -> None:
        """Initialize the runner pool.

        Args:
            max_runners: Maximum concurrent runners allowed globally (default: 5).
        """
        self.max_runners = max_runners
        self._lock = Lock()
        self._started_this_tick = 0

    def reset_tick(self) -> None:
        """Reset per-tick counter. Call at start of each scheduler tick."""
        with self._lock:
            self._started_this_tick = 0

    def get_started_this_tick(self) -> int:
        """Get the number of runners started this tick.

        Returns:
            Number of runners started in the current tick.
        """
        with self._lock:
            return self._started_this_tick

    def get_current_runners(self) -> int:
        """Get total current runners (global + started this tick).

        Returns:
            Total number of runners currently active or started this tick.
        """
        with self._lock:
            return count_all_runners_global() + self._started_this_tick

    def get_available_slots(self) -> int:
        """Get number of available runner slots.

        Returns:
            Number of additional runners that can be started.
        """
        with self._lock:
            current = count_all_runners_global() + self._started_this_tick
            return max(0, self.max_runners - current)

    def reserve_slot(self) -> bool:
        """Try to reserve a runner slot.

        Returns:
            True if slot reserved, False if at limit.
        """
        with self._lock:
            current = count_all_runners_global() + self._started_this_tick
            if current >= self.max_runners:
                return False
            self._started_this_tick += 1
            return True

    def reserve_slots(self, count: int) -> int:
        """Reserve up to `count` slots.

        Args:
            count: Maximum number of slots to reserve.

        Returns:
            Number of slots actually reserved.
        """
        with self._lock:
            current = count_all_runners_global() + self._started_this_tick
            available = max(0, self.max_runners - current)
            to_reserve = min(count, available)
            self._started_this_tick += to_reserve
            return to_reserve

    def add_started(self, count: int) -> None:
        """Add to the started count (used when external code starts runners).

        This is used when the actual runner starting is done by external code
        (like check_hooks) that reports back how many it started.

        Args:
            count: Number of runners that were started.
        """
        with self._lock:
            self._started_this_tick += count

    def is_at_limit(self) -> bool:
        """Check if runner limit has been reached.

        Returns:
            True if no more runners can be started, False otherwise.
        """
        return self.get_available_slots() == 0
