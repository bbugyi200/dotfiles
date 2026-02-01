# Gai Codebase Guidelines

## Backward Compatibility

This codebase has a single user who can update all files simultaneously. Breaking changes are acceptable without:

- Backward-compatibility shims
- Deprecation warnings
- Migration paths

When making changes, update ChangeSpecs and project spec files in the same commit as the code changes they depend on.
