--- A better annotation generator. Supports multiple languages and annotation conventions.

return {
	-- PLUGIN: http://github.com/danymat/neogen
	{
		"danymat/neogen",
		dependencies = "nvim-treesitter/nvim-treesitter",
		opts = { snippet_engine = "luasnip" },
		init = function()
			-- KEYMAP(N): <leader>ngc
			vim.keymap.set("n", "<leader>ngc", "<cmd>Neogen class<cr>", { desc = "Generate doc comment for class." })

			-- KEYMAP(N): <leader>ngf
			vim.keymap.set("n", "<leader>ngf", "<cmd>Neogen func<cr>", { desc = "Generate doc comment for function." })

			-- KEYMAP(N): <leader>ngg
			vim.keymap.set(
				"n",
				"<leader>ngg",
				"<cmd>Neogen<cr>",
				{ desc = "Generate doc comment based on context of current line." }
			)

			-- KEYMAP(N): <leader>ngm
			vim.keymap.set("n", "<leader>ngm", "<cmd>Neogen file<cr>", { desc = "Generate doc comment for module." })

			-- KEYMAP(N): <leader>ngt
			vim.keymap.set("n", "<leader>ngt", "<cmd>Neogen type<cr>", { desc = "Generate doc comment for type." })
		end,
	},
}
