--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.
--
-- P0: Save should have a keymap (,S) to pull, amend, commit, and push chezmoi directory!
-- P0: Use ,z prefix for ALL zorg keymaps (exs: ',x', '\z', 'zz0')!
-- P1: Add git presubmit to chezmoi repo!
-- P1: Write zorg snippet for 'NOTES:' bullet!
-- P1: Store last zorg command (ex: 'zz0') in the @z register?!
-- P1: Add cfg/lua to NeoVim runtime path and migrate cfg/zorg.lua to it!
-- P2: Create `autochez` script! Still necessary even with ,S keymap?
-- P2: Write install/update script for building/installing NeoVim from source!
--          (CMD: make CMAKE_BUILD_TYPE=RelWithDebInfo -j && sudo make CMAKE=/opt/homebrew/bin/cmake install)
-- P3: Browse the web using NeoVim: https://www.reddit.com/r/neovim/comments/1e31l02/browse_the_web_in_neovim
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
