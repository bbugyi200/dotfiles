"""Pytest configuration for gai tests."""

import sys
from pathlib import Path

# Add parent directory to path so we can import gai modules
sys.path.insert(0, str(Path(__file__).parent.parent))
