# GAI Configuration

## Gemini API Mode

GAI supports both CLI and direct API modes for interacting with Gemini.

### Environment Variables

To enable API mode, set the following environment variables:

#### Required
- `GAI_USE_GEMINI_API=true` - Enable API mode (default: false, uses CLI)

#### Optional (with defaults)
- `GAI_GEMINI_ENDPOINT=http://localhost:8649/predict` - API endpoint URL
- `GAI_GEMINI_MODEL=gemini-for-google-2.5-pro` - Model to use
- `GAI_GEMINI_TEMPERATURE=0.1` - Response randomness (0.0-1.0)
- `GAI_GEMINI_MAX_DECODER_STEPS=8192` - Maximum output tokens

### Example Usage

#### Enable API Mode (Bash)
```bash
export GAI_USE_GEMINI_API=true
export GAI_GEMINI_ENDPOINT=http://localhost:8649/predict
export GAI_GEMINI_MODEL=gemini-for-google-2.5-pro
export GAI_GEMINI_TEMPERATURE=0.1
export GAI_GEMINI_MAX_DECODER_STEPS=8192

# Run GAI workflow
gai fix-tests "pytest test_example.py" test_output.txt
```

#### Enable API Mode (Fish)
```fish
set -x GAI_USE_GEMINI_API true
set -x GAI_GEMINI_ENDPOINT http://localhost:8649/predict
set -x GAI_GEMINI_MODEL gemini-for-google-2.5-pro
set -x GAI_GEMINI_TEMPERATURE 0.1
set -x GAI_GEMINI_MAX_DECODER_STEPS 8192

# Run GAI workflow
gai fix-tests "pytest test_example.py" test_output.txt
```

#### One-liner for Testing
```bash
GAI_USE_GEMINI_API=true gai fix-tests "pytest test_example.py" test_output.txt
```

### Mode Selection

1. **CLI Mode (Default)**: Uses `/google/bin/releases/gemini-cli/tools/gemini` command
2. **API Mode**: Makes direct HTTP requests to the Gemini API endpoint

The wrapper will automatically fall back to CLI mode if:
- API client initialization fails
- Environment variables are invalid
- API endpoint is unreachable

### Benefits of API Mode

- **Better Error Handling**: More detailed error messages from API responses
- **Structured Requests**: Support for multi-turn conversations and system prompts
- **Flexible Configuration**: Easy to change models, endpoints, and parameters
- **Network Flexibility**: Can use remote endpoints or custom proxy servers
- **Debugging**: Better request/response logging and inspection

### Compatibility

Both modes support the same GAI workflow features:
- fix-tests workflow
- add-tests workflow
- Logging to gai.md files
- All agent types (planner, editor, research, verification)