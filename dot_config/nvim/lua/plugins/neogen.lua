--- A better annotation generator. Supports multiple languages and annotation conventions.

return {
	-- PLUGIN: http://github.com/danymat/neogen
	{
		"danymat/neogen",
		dependencies = "nvim-treesitter/nvim-treesitter",
		opts = { snippet_engine = "luasnip" },
		init = function()
			-- KEYMAP(N): <leader>nn
			vim.keymap.set(
				"n",
				"<leader>nn",
				"<cmd>Neogen<cr>",
				{ desc = "Generate doc comment based on context of current line." }
			)

			-- KEYMAP(N): <leader>nc
			vim.keymap.set("n", "<leader>nc", "<cmd>Neogen class<cr>", { desc = "Generate doc comment for class." })

			-- KEYMAP(N): <leader>nf
			vim.keymap.set(
				"n",
				"<leader>nf",
				"<cmd>Neogen function<cr>",
				{ desc = "Generate doc comment for function." }
			)

			-- KEYMAP(N): <leader>nm
			vim.keymap.set("n", "<leader>nm", "<cmd>Neogen file<cr>", { desc = "Generate doc comment for module." })

			-- KEYMAP(N): <leader>nt
			vim.keymap.set("n", "<leader>nt", "<cmd>Neogen type<cr>", { desc = "Generate doc comment for type." })
		end,
	},
}
