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

			-- KEYMAP: <leader>crc
			vim.keymap.set(
				"n",
				"<leader>crc",
				"<cmd>CritiqueHideAllComments<cr>",
				{ desc = "Hide all Critique comments." }
			)
			-- KEYMAP: <leader>crl
			vim.keymap.set(
				"n",
				"<leader>crl",
				"<cmd>CritiqueComments<cr>",
				{ desc = "Load Critique comments in buffer." }
			)
			-- KEYMAP: <leader>cro
			vim.keymap.set(
				"n",
				"<leader>cro",
				"<cmd>CritiqueShowAllComments<cr>",
				{ desc = "Show all Critique comments." }
			)
			-- KEYMAP: <leader>crO
			vim.keymap.set(
				"n",
				"<leader>crO",
				"<cmd>CritiqueShowUnresolvedComments<cr>",
				{ desc = "Show unresolved Critique comments." }
			)

			-- ────────────────────────── [C and ]C keymaps ──────────────────────────
			local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
			local goto_next, goto_prev = repeat_move.make_repeatable_move_pair(function()
				vim.cmd("CritiqueNextComment")
			end, function()
				vim.cmd("CritiquePreviousComment")
			end)

			-- KEYMAP: [C
			vim.keymap.set("n", "[C", goto_prev, { desc = "Goto next Critique comment.", nowait = true })
			-- KEYMAP: ]C
			vim.keymap.set("n", "]C", goto_next, { desc = "Goto previous Critique comment.", nowait = true })
		end,
	},
}
