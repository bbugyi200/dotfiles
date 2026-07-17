---
name: sase_artifact_file
description: Register files produced during an agent run as explicit SASE artifact files.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_artifact_file --reason "<one-line reason for using this skill>"
```

Use this skill when the user asks you to produce a file that should be available from the SASE Agents tab.

## Workflow

1. Create the requested file in your workspace.
2. Register it as an explicit artifact file:

   ```bash
   sase artifact-file create -p <path> -n "<label>"
   ```

3. Report the artifact-file id and stored path printed by the command.

## Options

- `-p, --path` is required and points to the file you created.
- `-n, --label` sets the artifact-file display name.
- `-k, --kind` may be one of `chat`, `plan`, `image`, `markdown`, `pdf`, or `file`. Omit it to infer from the file
  extension.

The command moves the file into SASE artifact-file storage, so do not edit the original path after registration.
