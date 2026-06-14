---
name: sase_artifact
description: Create explicit SASE artifacts from files produced during an agent run.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills log sase_artifact --reason "<one-line reason for using this skill>"
```

Use this skill when the user asks you to produce an artifact that should be available from the SASE Agents tab.

## Workflow

1. Create the requested file in your workspace.
2. Register it as an explicit artifact:

   ```bash
   sase artifact create -p <path> -n "<label>"
   ```

3. Report the artifact id and stored path printed by the command.

## Options

- `-p, --path` is required and points to the file you created.
- `-n, --label` sets the artifact display name.
- `-k, --kind` may be one of `chat`, `plan`, `image`, `markdown`, `pdf`, or `file`. Omit it to infer from the file
  extension.

The command moves the file into SASE artifact storage, so do not edit the original path after registration.
