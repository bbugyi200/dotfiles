--- A Neovim plugin that highlights Google-style terms (like bug references,
--- user mentions, and question IDs) inside comments and shows tooltips.

-- PLUGIN: http://go/goog-terms
return {
	{
		"vintharas/goog-terms.nvim",
		url = "sso://user/vintharas/goog-terms.nvim",
		lazy = true,
		ft = { "go", "python", "java", "javascript", "typescript", "lua" },
		opts = {
			tooltip_key = "<leader>gtt",
			action_key = "<leader>gta",
		},
		init = function()
			-- KEYMAP GROUP: <leader>gt
			vim.keymap.set("n", "<leader>gt", "<nop>", { desc = "goog-terms.nvim" })
		end,
	},
}
