# Chezmoi Dotfile Repo

This repository contains all of my dotfiles as well as a lot of my scripts (all of which live in the home/ directory),
some of which are pretty large (these tend to be Python projects in the home/lib/ directory).

## IMPORTANT: Always commit your changes using `bb_commit`!

After completing all file changes for a user's request, always use the `/commit` skill to create a commit. Never use raw `git commit` commands. The `/commit` skill will guide you through staging changes and creating a properly formatted conventional commit.

## Executable Scripts
Since this is a Chezmoi repo, all executable scripts in the home/ directory (which tend to live in home/bin) have
`executable_` prefixed to their filenames. These scripts will exist on this system's PATH as executables without the
prefix.
