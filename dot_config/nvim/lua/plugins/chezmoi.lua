--- Chezmoi plugin for neovim.

return {
	-- PLUGIN: http://github.com/xvzc/chezmoi.nvim
	{
		"xvzc/chezmoi.nvim",
		dependencies = { "nvim-telescope/telescope.nvim" },
		opts = {
			edit = {
				watch = true,
				force = false,
			},
			notification = {
				on_open = true,
				on_apply = true,
				on_watch = false,
			},
			telescope = {
				select = { "<CR>" },
			},
		},
		init = function()
			local telescope = require("telescope")

			-- KEYMAP(N): <leader>tz
			vim.keymap.set("n", "<leader>tz", telescope.extensions.chezmoi.find_files, {
				desc = "Telescope chezmoi",
			})
		end,
	},
}
