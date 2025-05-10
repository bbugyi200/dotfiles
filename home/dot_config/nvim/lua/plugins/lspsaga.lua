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
			--- Used to produce repeatable keymaps to jumpt to the next/previous diagnostic.
			---
			---@return function, function # The appropriate goto_next() and goto_prev() functions.
			local function get_goto_diags()
				local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
				return repeat_move.make_repeatable_move_pair(function()
					require("lspsaga.diagnostic"):goto_next()
				end, function()
					require("lspsaga.diagnostic"):goto_prev()
				end)
			end

			-- Enable virtual text and disable virtual lines by default.
			vim.diagnostic.config({ virtual_lines = false, virtual_text = true })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
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

			-- KEYMAP: [d
			vim.keymap.set("n", "[d", function()
				local _, goto_prev = get_goto_diags()
				goto_prev()
			end, { desc = "Goto previous diagnostic" })
			-- KEYMAP: ]d
			vim.keymap.set("n", "]d", function()
				local goto_next, _ = get_goto_diags()
				goto_next()
			end, { desc = "Goto next diagnostic" })
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
			-- KEYMAP: gI
			vim.keymap.set("n", "gI", "<cmd>lua vim.lsp.buf.implementation()<cr>", {
				desc = "Goto implementation",
			})
			-- KEYMAP: gr
			vim.keymap.set("n", "gr", "<cmd>Lspsaga finder<cr>", { desc = "Lspsaga finder" })
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
			-- KEYMAP: K
			vim.keymap.set("n", "K", vim.lsp.buf.hover, { desc = "Display preview of symbol's doc comment." })

			-- ─────────────────────── <leader>ls KEYMAP GROUP ───────────────────────
			-- KEYMAP GROUP: <leader>ls
			vim.keymap.set("n", "<leader>ls", "<nop>", { desc = "lspsaga.nvim" })
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
			-- KEYMAP GROUP: <leader>lsd
			vim.keymap.set("n", "<leader>lsd", "<nop>", { desc = "Lspsaga show_*_diagnostics" })
			-- KEYMAP: <leader>lsdb
			vim.keymap.set(
				"n",
				"<leader>lsdb",
				"<cmd>Lspsaga show_buffer_diagnostics<cr>",
				{ desc = "Lspsaga show_buffer_diagnostics" }
			)
			-- KEYMAP: <leader>lsdl
			vim.keymap.set("n", "<leader>lsdl", function()
				local virtual_lines = vim.diagnostic.config().virtual_lines
				local virtual_text = vim.diagnostic.config().virtual_text
				vim.diagnostic.config({ virtual_lines = not virtual_lines, virtual_text = not virtual_text })
			end, { desc = "Toggle diagnostics in virtual lines." })
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
