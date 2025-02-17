--- Chezmoi plugin for neovim.

return {
	-- PLUGIN: http://github.com/xvzc/chezmoi.nvim
	{
		"xvzc/chezmoi.nvim",
		dependencies = { "nvim-telescope/telescope.nvim" },
		opts = {},
		init = function()
			local telescope = require("telescope")

			-- KEYMAP(N): <leader>tz
			vim.keymap.set("n", "<leader>tz", telescope.extensions.chezmoi.find_files, {
				desc = "Telescope chezmoi",
			})
		end,
	},
	-- PLUGIN: http://github.com/alker0/chezmoi.vim
	{
		"alker0/chezmoi.vim",
		lazy = false,
		init = function()
			-- This option is required.
			-- (see https://github.com/alker0/chezmoi.vim#-how-can-i-make-it-work-with-lazynvim)
			vim.g["chezmoi#use_tmp_buffer"] = true
		end,
	},
}
