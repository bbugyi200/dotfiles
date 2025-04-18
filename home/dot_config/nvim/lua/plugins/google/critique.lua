--- Display Critique comments inline with your code. Critique comments,
--- selections, and replies are rendered as virtual text in a threaded format
--- for maximum readability.

return {
	-- PLUGIN: http://go/critique-nvim
	{
		name = "critique-nvim",
		url = "sso://googler@user/cnieves/critique-nvim",
		main = "critique.comments",
		dependencies = {
			"rktjmp/time-ago.vim",
			"nvim-lua/plenary.nvim",
			"nvim-telescope/telescope.nvim",
			"runiq/neovim-throttle-debounce",
		},
		opts = {},
		init = function()
			-- KEYMAP GROUP: <leader>cr
			vim.keymap.set("n", "<leader>cr", "<nop>", { desc = "critique.nvim" })

			-- KEYMAP: <leader>cra
			vim.keymap.set(
				"n",
				"<leader>cra",
				"<cmd>CritiqueToggleAllComments<cr>",
				{ desc = "Toggle all Critique comments." }
			)

			-- KEYMAP: <leader>crc
			vim.keymap.set(
				"n",
				"<leader>crc",
				"<cmd>CritiqueComments<cr>",
				{ desc = "Load Critique comments in buffer." }
			)

			-- KEYMAP: <leader>crn
			vim.keymap.set("n", "<leader>crn", "<cmd>CritiqueNextComment<cr>", { desc = "Goto next Critique comment." })

			-- KEYMAP: <leader>crp
			vim.keymap.set(
				"n",
				"<leader>crp",
				"<cmd>CritiquePreviousComment<cr>",
				{ desc = "Goto previous Critique comment." }
			)

			-- KEYMAP: <leader>cru
			vim.keymap.set(
				"n",
				"<leader>cru",
				"<cmd>CritiqueToggleUnresolvedComments<cr>",
				{ desc = "Toggle unresolved Critique comments." }
			)
		end,
	},
}
