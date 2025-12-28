"""Terminal input utilities for the work workflow."""

import select
import sys
import termios
import time
import tty

from rich.console import Console


def wait_for_user_input() -> None:
    """Wait for the user to press any key to continue."""
    print("\nPress any key to continue...", end="", flush=True)

    # Save current terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode to read a single character
        tty.setraw(fd)
        sys.stdin.read(1)
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Print newline after the key press
        print()


def input_with_timeout(
    timeout_seconds: int, initial_input: str = ""
) -> tuple[str | None, str]:
    """Read a line of input with a timeout, preserving partial input.

    Uses raw terminal mode to read characters one at a time, allowing us to
    preserve any partial input if a timeout occurs.

    Args:
        timeout_seconds: Maximum seconds to wait for input (0 means no timeout)
        initial_input: Previously typed partial input to restore

    Returns:
        Tuple of (completed_input, partial_input):
        - If user completes input (presses Enter): (input_string, "")
        - If timeout occurs: (None, partial_input_so_far)

    Raises:
        EOFError: If EOF is encountered
        KeyboardInterrupt: If Ctrl+C is pressed
    """
    if timeout_seconds <= 0:
        # No timeout, use regular input (but still handle initial_input)
        if initial_input:
            # Print the initial input so user sees it
            print(initial_input, end="", flush=True)
        result = input()
        return (initial_input + result).strip(), ""

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer = initial_input

    # Print initial input if any
    if initial_input:
        print(initial_input, end="", flush=True)

    try:
        # Set terminal to cbreak mode (non-canonical, no echo)
        tty.setcbreak(fd)

        deadline = time.time() + timeout_seconds

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                # Timeout - return None with partial input
                print()  # Move to next line
                return None, buffer

            # Wait for input with remaining timeout
            ready, _, _ = select.select([sys.stdin], [], [], remaining)

            if not ready:
                # Timeout - return None with partial input
                print()  # Move to next line
                return None, buffer

            # Read one character
            char = sys.stdin.read(1)

            if not char:
                raise EOFError()

            if char == "\x03":  # Ctrl+C
                raise KeyboardInterrupt()

            if char == "\x04":  # Ctrl+D (EOF)
                raise EOFError()

            if char in ("\r", "\n"):  # Enter
                print()  # Move to next line
                return buffer.strip(), ""

            if char == "\x7f" or char == "\x08":  # Backspace (DEL or BS)
                if buffer:
                    buffer = buffer[:-1]
                    # Erase character on screen: move back, space, move back
                    print("\b \b", end="", flush=True)
            else:
                # Regular character - add to buffer and echo
                buffer += char
                print(char, end="", flush=True)

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def countdown_with_quit(console: Console, seconds: int = 10) -> bool:
    """Display countdown and wait for quit or timeout.

    Shows "Refreshing in N... [q]uit" and counts down, updating in place.
    Listens for 'q' key press to quit immediately.

    Args:
        console: Rich Console for output
        seconds: Countdown duration (default 10)

    Returns:
        True if user pressed 'q' to quit, False if countdown completed
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to cbreak mode (non-canonical, no echo)
        tty.setcbreak(fd)

        for remaining in range(seconds, 0, -1):
            # Clear line and print countdown (using carriage return to overwrite)
            console.print(
                f"\rRefreshing in {remaining}... [bold][q][/bold]uit",
                end="",
            )

            # Wait up to 1 second for input
            ready, _, _ = select.select([sys.stdin], [], [], 1.0)

            if ready:
                char = sys.stdin.read(1)
                if char.lower() == "q":
                    console.print()  # Move to next line
                    return True
                # Ignore other keys

        # Countdown completed
        console.print()  # Move to next line
        return False

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
