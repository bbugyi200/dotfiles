# SASE Memory

## Sibling Repositories

Configured sibling repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source.

When a sibling repository needs changes, agents MUST run:

```bash
sase workspace open -p <sibling_repo> <workspace_num>
```

`<workspace_num>` must be the workspace number assigned to the primary repo. Use the path printed by
`sase workspace open` as the only repository path for sibling edits.
