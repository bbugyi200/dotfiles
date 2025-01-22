--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.
--
-- P1: Save should have a keymap (,S) to pull, amend, commit, and push chezmoi directory!
-- P1: Use ,z prefix for ALL zorg keymaps (exs: ',x', '\z', 'zz0')!
-- P1: Add git presubmit to chezmoi repo!
-- P1: Write zorg snippet for 'NOTES:' bullet!
-- P1: Store last zorg command (ex: 'zz0') in the @z register?!
-- P1: Add cfg/lua to NeoVim runtime path and migrate cfg/zorg.lua to it!
-- P2: Write a function similar to `SetupCommandAlias()` from Modern Vim book?!
-- P2: Set VISUAL=nvim in .profile!
-- P2: Add module-level comments to all Lua files!
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

-- Define a function to execute selected lines
local function execute_selected_code()
	-- Get the visual selection
	local _, start_row, start_col, _ = unpack(vim.fn.getpos("'<"))
	local _, end_row, end_col, _ = unpack(vim.fn.getpos("'>"))

	-- Get the lines of the selection
	local lines = vim.api.nvim_buf_get_lines(0, start_row - 1, end_row, false)

	-- Combine lines and trim selection to the exact column range
	local code = table.concat(lines, "\n")
	if #lines == 1 then
		code = string.sub(code, start_col, end_col)
	else
		lines[1] = string.sub(lines[1], start_col)
		lines[#lines] = string.sub(lines[#lines], 1, end_col)
		code = table.concat(lines, "\n")
	end

	-- Execute the code as a Vim command
	vim.cmd(code)
end

-- Register the function as a Vim command
vim.api.nvim_create_user_command("ExecuteVisual", execute_selected_code, {})
