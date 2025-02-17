--- Chezmoi plugin for neovim.

return {
	-- PLUGIN: http://github.com/xvzc/chezmoi.nvim
	{
		"xvzc/chezmoi.nvim",
		dependencies = { "nvim-lua/plenary.nvim" },
		opts = {},
		init = function()
			-- KEYMAP(N): <leader>tz
			vim.keymap.set("n", "<leader>tz", "<cmd>Telescope chezmoi find_files<cr>", {
				desc = "Telescope chezmoi find_files",
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
