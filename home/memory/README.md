# SASE Memory

The `memory/` directory holds agent-facing project context. Use `sase memory list` to inspect what a launch would load
or reference, and `sase memory init` to create or refresh generated memory files.

- `memory/short/` contains short-term context that is loaded when an instruction root reaches it through an
  `@memory/...` reference.
- `memory/long/` contains detailed long-term context. Plain `memory/...` mentions make files visible as references, but
  do not load file contents unless the file is also reached through an `@...` reference.
