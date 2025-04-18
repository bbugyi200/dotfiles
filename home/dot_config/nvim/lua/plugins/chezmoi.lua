--- Chezmoi plugins for neovim:
---
--- * xvzc/chezmoi.nvim  | Designed to assist in editing and applying chezmoi-managed files.
--- * alker0/chezmoi.vim | Highlight dotfiles you manage with chezmoi.
--
-- P2: Write run_* script that installs system packages?!
--     (see file:///Users/bbugyi/org/manual/chezmoi_user_guide.pdf#page=8)

return {
	-- PLUGIN: http://github.com/xvzc/chezmoi.nvim
	{
		"xvzc/chezmoi.nvim",
		dependencies = { "nvim-lua/plenary.nvim" },
		opts = {},
		init = function()
			-- KEYMAP: <leader>tz
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
