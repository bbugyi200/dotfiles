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
	spec = {
		-- Import your plugins.
		{ import = "plugins" },
	},
	-- Set the colorscheme that will be used when installing plugins.
	install = { missing = true, colorscheme = { "desert" } },
	-- Use chezmoi lockfile!
	lockfile = os.getenv("HOME") .. "/.local/share/chezmoi/dot_config/nvim/lazy-lock.json",
	-- Automatically check for plugin updates
	checker = { enabled = true },
	-- Automatically check for config file changes, but do NOT notify me about them.
	change_detection = {
		enabled = true,
		notify = false,
	},
})

vim.keymap.set("n", "<leader>L", "<cmd>Lazy<cr>", { desc = "Run `:Lazy` command." })
vim.keymap.set("n", "<leader>lu", "<cmd>Lazy update<cr>", { desc = "Run `:Lazy update` command." })
vim.keymap.set("n", "<leader>lx", "<cmd>Lazy clean<cr>", { desc = "Run `:Lazy clean` command." })
