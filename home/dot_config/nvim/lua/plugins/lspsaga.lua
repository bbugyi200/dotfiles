--- Improves the Neovim built-in LSP experience.

return {
	-- PLUGIN: http://github.com/nvimdev/lspsaga.nvim
	{
		"nvimdev/lspsaga.nvim",
		opts = {},
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"nvim-tree/nvim-web-devicons",
		},
		init = function()
			-- KEYMAP: ga
			vim.keymap.set(
				"n",
				"ga",
				"<cmd>Lspsaga code_action<cr>",
				{ desc = "Get code actions for the current line." }
			)
			-- KEYMAP: <c-]>
			-- KEYMAP: gd
			for _, lhs in ipairs({ "<c-]>", "gd" }) do
				vim.keymap.set("n", lhs, "<cmd>Lspsaga goto_definition<cr>", {
					desc = "Goto definition.",
				})
			end
			-- KEYMAP: gR
			vim.keymap.set("n", "gR", "<cmd>Lspsaga rename<cr>", {
				desc = "Rename symbol under cursor.",
			})
			-- KEYMAP: gt
			vim.keymap.set(
				"n",
				"gt",
				"<cmd>Lspsaga goto_type_definition<cr>",
				{ desc = "Lspsaga goto_type_definition" }
			)

			-- ────────────────────────────── gr KEYMAP ──────────────────────────────
			-- Unmap builtin keymaps that would slow down the 'gr' keymap defined in this file.
			local lhs_to_unmap = { "gra", "gri", "grn", "grr" }
			for _, lhs in ipairs(lhs_to_unmap) do
				if vim.fn.maparg(lhs, "n") ~= "" then
					vim.keymap.del("n", lhs)
				end
				if vim.fn.maparg(lhs, "x") ~= "" then
					vim.keymap.del("x", lhs)
				end
			end
			-- KEYMAP: gr
			vim.keymap.set("n", "gr", "<cmd>Lspsaga finder<cr>", { desc = "Lspsaga finder" })

			-- ────────────────────────── [d AND ]d KEYMAPS ──────────────────────────
			local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
			local goto_next, goto_prev = repeat_move.make_repeatable_move_pair(function()
				require("lspsaga.diagnostic"):goto_next()
			end, function()
				require("lspsaga.diagnostic"):goto_prev()
			end)
			-- KEYMAP: [d
			vim.keymap.set("n", "[d", goto_prev, { desc = "Goto previous diagnostic" })
			-- KEYMAP: ]d
			vim.keymap.set("n", "]d", goto_next, { desc = "Goto next diagnostic" })

			-- ─────────────────────── <leader>ls KEYMAP GROUP ───────────────────────
			-- KEYMAP GROUP: <leader>lsc
			vim.keymap.set("n", "<leader>lsc", "<nop>", { desc = "Lspsaga *_calls" })
			-- KEYMAP: <leader>lsci
			vim.keymap.set("n", "<leader>lsci", "<cmd>Lspsaga incoming_calls<cr>", {
				desc = "Lspsaga incoming_calls",
			})
			-- KEYMAP: <leader>lsco
			vim.keymap.set("n", "<leader>lsco", "<cmd>Lspsaga outgoing_calls<cr>", {
				desc = "Lspsaga outgoing_calls",
			})
			-- KEYMAP: <leader>lsdb
			vim.keymap.set(
				"n",
				"<leader>lsdb",
				"<cmd>Lspsaga show_buffer_diagnostics<cr>",
				{ desc = "Lspsaga show_buffer_diagnostics" }
			)
			-- KEYMAP: <leader>lsdw
			vim.keymap.set(
				"n",
				"<leader>lsdw",
				"<cmd>Lspsaga show_workspace_diagnostics<cr>",
				{ desc = "Lspsaga show_workspace_diagnostics" }
			)
			-- KEYMAP: <leader>lso
			vim.keymap.set("n", "<leader>lso", "<cmd>Lspsaga outline<cr>", { desc = "Lspsaga outline" })
			-- KEYMAP GROUP: <leader>lsp
			vim.keymap.set("n", "<leader>lsp", "<nop>", { desc = "Lspsaga peek_*_definition" })
			-- KEYMAP: <leader>lspd
			vim.keymap.set("n", "<leader>lspd", "<cmd>Lspsaga peek_definition<cr>", {
				desc = "Lspsaga peek_definition",
			})
			-- KEYMAP: <leader>lspt
			vim.keymap.set(
				"n",
				"<leader>lspt",
				"<cmd>Lspsaga peek_type_definition<cr>",
				{ desc = "Lspsaga peek_type_definition" }
			)
			-- KEYMAP: <leader>lsr
			vim.keymap.set(
				"n",
				"<leader>lsr",
				"<cmd>Lspsaga rename ++project<cr>",
				{ desc = "Lspsaga rename ++project" }
			)
		end,
	},
}
