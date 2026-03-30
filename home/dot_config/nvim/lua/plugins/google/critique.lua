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
			-- For repeatable motions using { and }.
			"nvim-treesitter/nvim-treesitter-textobjects",
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

			-- ─────── KEYMAPS TO NAVIGATE TO NEXT/PREVIOUS CRITIQUE COMMENTS ────
			local repeat_move = require("bb_utils").require_repeatable_move()
			local move_critique = repeat_move.make_repeatable_move(function(opts)
				if opts.forward then
					vim.cmd("CritiqueNextComment")
				else
					vim.cmd("CritiquePreviousComment")
				end
			end)

			-- KEYMAP: <leader>crn
			vim.keymap.set("n", "<leader>crn", function()
				move_critique({ forward = true })
			end, { desc = "Goto next Critique comment." })
			-- KEYMAP: <leader>crp
			vim.keymap.set("n", "<leader>crp", function()
				move_critique({ forward = false })
			end, { desc = "Goto previous Critique comment." })
		end,
	},
}
