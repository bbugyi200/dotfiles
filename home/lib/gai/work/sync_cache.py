"""Cache for tracking when ChangeSpecs were last checked for submission."""

import json
import time
from pathlib import Path

# Minimum interval between checks in seconds (5 minutes)
MIN_CHECK_INTERVAL_SECONDS = 5 * 60

# Cache file location
_CACHE_FILE = Path.home() / ".gai" / "sync_cache.json"


def _load_cache() -> dict[str, float]:
    """Load the sync cache from disk.

    Returns:
        Dictionary mapping ChangeSpec names to last_checked timestamps (Unix time).
    """
    if not _CACHE_FILE.exists():
        return {}

    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict[str, float]) -> None:
    """Save the sync cache to disk.

    Args:
        cache: Dictionary mapping ChangeSpec names to last_checked timestamps.
    """
    # Ensure parent directory exists
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass  # Silently fail if we can't write the cache


def _get_last_checked(changespec_name: str) -> float | None:
    """Get the last time a ChangeSpec was checked for submission.

    Args:
        changespec_name: The NAME field value of the ChangeSpec.

    Returns:
        Unix timestamp of last check, or None if never checked.
    """
    cache = _load_cache()
    return cache.get(changespec_name)


def update_last_checked(changespec_name: str) -> None:
    """Update the last_checked timestamp for a ChangeSpec to now.

    Args:
        changespec_name: The NAME field value of the ChangeSpec.
    """
    cache = _load_cache()
    cache[changespec_name] = time.time()
    _save_cache(cache)


def should_check(changespec_name: str, min_interval: int | None = None) -> bool:
    """Determine if a ChangeSpec should be checked for submission.

    A ChangeSpec should be checked if it has never been checked before,
    or if at least min_interval seconds have passed since the last check.

    Args:
        changespec_name: The NAME field value of the ChangeSpec (or a cache key).
        min_interval: Minimum interval in seconds. Defaults to MIN_CHECK_INTERVAL_SECONDS.

    Returns:
        True if the ChangeSpec should be checked, False otherwise.
    """
    if min_interval is None:
        min_interval = MIN_CHECK_INTERVAL_SECONDS

    last_checked = _get_last_checked(changespec_name)

    if last_checked is None:
        return True

    elapsed = time.time() - last_checked
    return elapsed >= min_interval


def clear_cache_entry(changespec_name: str) -> None:
    """Remove a ChangeSpec from the cache.

    Useful when a ChangeSpec's status changes to Submitted.

    Args:
        changespec_name: The NAME field value of the ChangeSpec.
    """
    cache = _load_cache()
    if changespec_name in cache:
        del cache[changespec_name]
        _save_cache(cache)
