#!/usr/bin/env python3
"""
Simple test script to verify Gemini API mode works correctly.
"""

import os
import sys
from langchain_core.messages import HumanMessage

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(__file__))

from gemini_wrapper import GeminiCommandWrapper


def test_cli_mode():
    """Test CLI mode (default)."""
    print("Testing CLI mode...")
    wrapper = GeminiCommandWrapper(use_api=False)

    messages = [
        HumanMessage(content="Hello, can you respond with just 'CLI mode working'?")
    ]
    response = wrapper.invoke(messages)

    print(f"CLI Response: {response.content}")
    return "CLI mode working" in response.content.lower()


def test_api_mode():
    """Test API mode."""
    print("Testing API mode...")

    # Set environment variables for testing
    os.environ["GAI_USE_GEMINI_API"] = "true"
    os.environ["GAI_GEMINI_ENDPOINT"] = "http://localhost:8649/predict"

    wrapper = GeminiCommandWrapper(use_api=True)

    if not wrapper.use_api:
        print("API mode not available (falling back to CLI)")
        return False

    messages = [
        HumanMessage(content="Hello, can you respond with just 'API mode working'?")
    ]
    response = wrapper.invoke(messages)

    print(f"API Response: {response.content}")
    return "API mode working" in response.content.lower()


def test_automatic_detection():
    """Test automatic mode detection via environment variable."""
    print("Testing automatic mode detection...")

    # Test with API enabled
    os.environ["GAI_USE_GEMINI_API"] = "true"
    wrapper = GeminiCommandWrapper()  # No explicit mode

    print(f"Auto-detected mode: {'API' if wrapper.use_api else 'CLI'}")

    # Test with API disabled
    os.environ["GAI_USE_GEMINI_API"] = "false"
    wrapper = GeminiCommandWrapper()  # No explicit mode

    print(f"Auto-detected mode: {'API' if wrapper.use_api else 'CLI'}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("GAI Gemini API Mode Test")
    print("=" * 60)

    tests = [
        ("Automatic Mode Detection", test_automatic_detection),
        ("CLI Mode", test_cli_mode),
        ("API Mode", test_api_mode),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results[test_name] = False

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("\nUsage Instructions:")
    print("- Set GAI_USE_GEMINI_API=true to enable API mode")
    print("- Ensure your DevAI server is running on the configured endpoint")
    print("- Use environment variables to configure endpoint, model, etc.")


if __name__ == "__main__":
    main()
