--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.
--
-- P1: Add ~/prg/cfg/lua to NeoVim runtime path and migrate ~/org/cfg/zorg.lua to it!
-- P1: Move chezmoi files to home/ subdir!
-- P2: Add keymaps and plugin recommended by ~/org/img/nvim_tmux_nav.png?
-- P2: Make it harder to nest nvim in terminal buffer:
--   [ ] Give unique highlighting to terminal mode cursor (see ~/org/img/nvim_hi_term_cursor.png)?
--   [ ] Add indication to shell prompt (see ~/org/img/nvim_term_prompt.png)?
--   [ ] Alias 'nvim' to 'nvr' when inside a terminal buffer (see ~/org/img/nvim_nvr_alias.png)?
-- P2: Store last zorg command (ex: 'zz0') in the @z register?!
-- P2: Make chezmoi commits / pushes automatic / easy. Options:
--   1) Save should have a keymap (,S) to pull, amend, commit, and push chezmoi directory?
--   2) Use watchman?
--   3) Create `autochez` script!
-- P2: Use ,z prefix for ALL zorg keymaps (exs: ',x', '\z', 'zz0')!
-- P2: Add git presubmit to chezmoi repo!
-- P2: Write a function similar to `SetupCommandAlias()` from Modern Vim book?!
-- P2: Set VISUAL=nvim in .profile!
-- P2: Add module-level comments to all Lua files!
-- P2: Write install/update script for building/installing NeoVim from source!
--          (CMD: make CMAKE_BUILD_TYPE=RelWithDebInfo -j && sudo make CMAKE=/opt/homebrew/bin/cmake install)
-- P3: Browse the web using NeoVim: https://www.reddit.com/r/neovim/comments/1e31l02/browse_the_web_in_neovim
-- P4: Implement 'string.startswith()' for ALL string types!
-- P4: Walk through vimrc line by line.
-- P4: Walk through plugins.vim line by line.
-- P4: Test nvim built-in terminal support!
-- P4: Fix annoying notification in *.zo files!

-- Configuration that needs to be loaded FIRST (e.g. to set mapleader).
require("config.preload")
-- Configure settings / options that are NOT specific to a plugin.
require("config.options")
-- Configure keymaps that are NOT specific to a plugin.
require("config.keymaps")
-- Configure autocmds that are NOT specific to a plugin.
require("config.autocmds")
-- Configure lazy.nvim and ALL plugins specified via plugins/*.lua files!
require("config.lazy_plugins")
-- Load (aka source) local vimrc and init.lua files.
require("config.load_local_configs")
