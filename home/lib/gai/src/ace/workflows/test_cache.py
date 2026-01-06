"""Test output caching system for bb_rabbit_test.

This module provides functionality to cache test outputs based on:
- Test targets
- Current diff from hg pdiff

This allows skipping redundant test runs when the code and test targets haven't changed.
"""

import hashlib
import os
import subprocess
from dataclasses import dataclass

from rich.console import Console


@dataclass
class _TestCacheResult:
    """Result of a test cache lookup."""

    cache_hit: bool
    cache_file: str | None = None
    output_content: str | None = None


def _get_cache_dir() -> str:
    """Get the test cache directory path.

    Returns:
        Path to ~/.gai/test_cache directory
    """
    cache_dir = os.path.expanduser("~/.gai/test_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _generate_hash(test_targets: str, diff_output: str) -> str:
    """Generate a hash from test targets and diff output.

    Args:
        test_targets: Space-separated test targets string
        diff_output: Output from hg pdiff command

    Returns:
        SHA256 hash string
    """
    # Combine test targets and diff for hashing
    combined = f"{test_targets}\n---DIFF---\n{diff_output}"
    return hashlib.sha256(combined.encode()).hexdigest()


def _get_hg_pdiff(target_dir: str, console: Console) -> str | None:
    """Get the output of hg pdiff command.

    Args:
        target_dir: Directory to run hg pdiff in
        console: Rich console for output

    Returns:
        The diff output, or None if command fails
    """
    try:
        result = subprocess.run(
            ["hg", "pdiff"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        else:
            console.print(
                f"[yellow]Warning: hg pdiff failed with code {result.returncode}[/yellow]"
            )
            return None
    except subprocess.TimeoutExpired:
        console.print("[yellow]Warning: hg pdiff timed out[/yellow]")
        return None
    except FileNotFoundError:
        console.print("[yellow]Warning: hg command not found[/yellow]")
        return None
    except Exception as e:
        console.print(f"[yellow]Warning: Error running hg pdiff: {str(e)}[/yellow]")
        return None


def check_test_cache(
    test_targets: str, target_dir: str, console: Console
) -> _TestCacheResult:
    """Check if cached test output exists for the given test targets and current diff.

    Args:
        test_targets: Space-separated test targets string
        target_dir: Directory to run hg pdiff in
        console: Rich console for output

    Returns:
        _TestCacheResult with cache hit status and cached content if available
    """
    # Get current diff
    diff_output = _get_hg_pdiff(target_dir, console)
    if diff_output is None:
        # Can't use cache if we can't get the diff
        console.print("[cyan]Skipping test cache check (could not get hg pdiff)[/cyan]")
        return _TestCacheResult(cache_hit=False)

    # Generate hash
    cache_hash = _generate_hash(test_targets, diff_output)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_hash}.txt")

    # Check if cache file exists
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                content = f.read()
            console.print(
                f"[green]Found cached test output (hash: {cache_hash[:12]}...)[/green]"
            )
            return _TestCacheResult(
                cache_hit=True, cache_file=cache_file, output_content=content
            )
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not read cache file: {str(e)}[/yellow]"
            )
            return _TestCacheResult(cache_hit=False)

    console.print(
        f"[cyan]No cached test output found (hash: {cache_hash[:12]}...)[/cyan]"
    )
    return _TestCacheResult(cache_hit=False)


def save_test_output(
    test_targets: str,
    target_dir: str,
    test_output_content: str,
    console: Console,
) -> bool:
    """Save test output to cache.

    Args:
        test_targets: Space-separated test targets string
        target_dir: Directory to run hg pdiff in
        test_output_content: The full test output to cache
        console: Rich console for output

    Returns:
        True if saved successfully, False otherwise
    """
    # Get current diff
    diff_output = _get_hg_pdiff(target_dir, console)
    if diff_output is None:
        # Don't cache if we can't get the diff
        console.print(
            "[cyan]Skipping test output caching (could not get hg pdiff)[/cyan]"
        )
        return False

    # Generate hash
    cache_hash = _generate_hash(test_targets, diff_output)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_hash}.txt")

    try:
        with open(cache_file, "w") as f:
            f.write(test_output_content)
        console.print(f"[green]Cached test output (hash: {cache_hash[:12]}...)[/green]")
        return True
    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not cache test output: {str(e)}[/yellow]"
        )
        return False
