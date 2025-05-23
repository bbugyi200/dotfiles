--- A better annotation generator. Supports multiple languages and annotation conventions.

return {
	-- PLUGIN: http://github.com/danymat/neogen
	{
		"danymat/neogen",
		dependencies = "nvim-treesitter/nvim-treesitter",
		opts = { snippet_engine = "luasnip" },
		init = function()
			-- KEYMAP GROUP: <leader>ng
			vim.keymap.set("n", "<leader>ng", "<nop>", { desc = "Neogen" })

			-- KEYMAP: <leader>ngc
			vim.keymap.set("n", "<leader>ngc", "<cmd>Neogen class<cr>", { desc = "Generate doc comment for class." })

			-- KEYMAP: <leader>ngf
			vim.keymap.set("n", "<leader>ngf", "<cmd>Neogen func<cr>", { desc = "Generate doc comment for function." })

			-- KEYMAP: <leader>ngg
			vim.keymap.set(
				"n",
				"<leader>ngg",
				"<cmd>Neogen<cr>",
				{ desc = "Generate doc comment based on context of current line." }
			)

			-- KEYMAP: <leader>ngm
			vim.keymap.set("n", "<leader>ngm", "<cmd>Neogen file<cr>", { desc = "Generate doc comment for module." })

			-- KEYMAP: <leader>ngt
			vim.keymap.set("n", "<leader>ngt", "<cmd>Neogen type<cr>", { desc = "Generate doc comment for type." })
		end,
	},
}
