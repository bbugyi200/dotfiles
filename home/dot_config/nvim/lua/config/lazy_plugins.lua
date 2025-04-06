-- P2: Migrate most of the keymaps in plugins/* files to the 'keys' table in
--     lazy.nvim to enable lazy loading?!
-- P4: Create ~/.editorconfig file?
-- P4: Remove all references to disabled nvim-spectre plugin!

-- Bootstrap lazy.nvim
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
	local lazyrepo = "https://github.com/folke/lazy.nvim.git"
	local out = vim.fn.system({
		"git",
		"clone",
		"--filter=blob:none",
		"--branch=stable",
		lazyrepo,
		lazypath,
	})
	if vim.v.shell_error ~= 0 then
		vim.api.nvim_echo({
			{ "Failed to clone lazy.nvim:\n", "ErrorMsg" },
			{ out, "WarningMsg" },
			{ "\nPress any key to exit..." },
		}, true, {})
		vim.fn.getchar()
		os.exit(1)
	end
end
vim.opt.rtp:prepend(lazypath)

-- Setup lazy.nvim
require("lazy").setup({
	-- Import plugins from the plugins/* directory.
	--
	-- NOTE: Additional plugins can be added directly to the `spec` table.
	spec = { { import = "plugins" } },
	-- Set the colorscheme that will be used when installing plugins.
	install = { missing = true, colorscheme = { "desert" } },
	-- Automatically check for plugin updates
	checker = { enabled = true },
	-- Automatically check for config file changes, but do NOT notify me about them.
	change_detection = {
		enabled = true,
		notify = false,
	},
})

-- Keymaps for the `:Lazy` command.
vim.keymap.set("n", "<leader>lz", "<nop>", { desc = "Lazy.nvim" })
-- KEYMAP: <leader>ll
vim.keymap.set("n", "<leader>lzl", "<cmd>Lazy<cr>", { desc = "Run `:Lazy` command." })
-- KEYMAP: <leader>lu
vim.keymap.set("n", "<leader>lzu", "<cmd>Lazy update<cr>", { desc = "Run `:Lazy update` command." })
-- KEYMAP: <leader>lx
vim.keymap.set("n", "<leader>lzx", "<cmd>Lazy clean<cr>", { desc = "Run `:Lazy clean` command." })
