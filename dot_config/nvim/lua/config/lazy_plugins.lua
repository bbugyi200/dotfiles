-- P1: Add enabled=false to all plugins in plugins/*.lua files?!

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
		-- { "akinsho/bufferline.nvim", enabled = true },
		-- { "folke/which-key.nvim", enabled = true },
		-- { "mhinz/vim-signify", enabled = true },
		-- { "nvim-tree/nvim-tree.lua", enabled = true },
		-- { "stevearc/conform.nvim", enabled = true },
		-- { "L3MON4D3/LuaSnip", enabled = true },
		-- { "nvim-pack/nvim-spectre", enabled = true },
		-- { "nvim-treesitter/nvim-treesitter", enabled = true },
		-- { "nvim-lualine/lualine.nvim", enabled = true },
		-- { "folke/trouble.nvim", enabled = true },
		-- { "zbirenbaum/copilot.lua", enabled = true },
		-- { "hrsh7th/nvim-cmp", enabled = true },
		-- { "nvim-telescope/telescope.nvim", enabled = true },
		-- { "neovim/nvim-lspconfig", enabled = true },
		-- { "rmagatti/auto-session", enabled = true },
		-- { "rcarriga/nvim-notify", enabled = true },
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

-- Keymaps for the `:Lazy` command.
vim.keymap.set("n", "<leader>ll", "<cmd>Lazy<cr>", { desc = "Run `:Lazy` command." })
vim.keymap.set("n", "<leader>lu", "<cmd>Lazy update<cr>", { desc = "Run `:Lazy update` command." })
vim.keymap.set("n", "<leader>lx", "<cmd>Lazy clean<cr>", { desc = "Run `:Lazy clean` command." })
