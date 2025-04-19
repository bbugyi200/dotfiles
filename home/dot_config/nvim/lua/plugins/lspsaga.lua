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
				return repeat_move.make_repeatable_move_pair(vim.diagnostic.goto_next, vim.diagnostic.goto_prev)
			end

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
			-- KEYMAP: g0
			vim.keymap.set("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", {
				desc = "List document symbols",
			})
			-- KEYMAP: ga
			vim.keymap.set(
				"n",
				"ga",
				"<cmd>Lspsaga code_action<cr>",
				{ desc = "Get code actions for the current line." }
			)
			-- KEYMAP: gd
			vim.keymap.set(
				"n",
				"gd",
				"<cmd>Lspsaga goto_type_definition<cr>",
				{ desc = "[lspsaga] Goto Type Definition." }
			)
			-- KEYMAP: gD
			vim.keymap.set("n", "gD", "<cmd>lua vim.lsp.buf.definition()<CR>", {
				desc = "Goto definition",
			})
			-- KEYMAP: gi
			vim.keymap.set("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", {
				desc = "Goto implementation",
			})
			-- KEYMAP: gr
			vim.keymap.set("n", "gr", "<cmd>Lspsaga finder<cr>", { desc = "[lspsaga] Activate Finder" })
			-- KEYMAP: gR
			vim.keymap.set("n", "gR", "<cmd>Lspsaga rename<cr>", {
				desc = "Rename symbol under cursor.",
			})
			-- KEYMAP: K
			vim.keymap.set("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", {
				desc = "List workspace symbols",
			})
		end,
	},
}
