--- Provides :TransformCode command that lets LLMs modify current file/selection.

-- PLUGIN: http://go/ai.nvim
return {
	{
		url = "sso://user/vvvv/ai.nvim",
		branch = "main",
		dependencies = {
			"rcarriga/nvim-notify",
			"nvim-lua/plenary.nvim",
		},
		opts = {
			transformcode_config = {
				model = "goose-v3.5-m",
			},
		},
		init = function()
			-- KEYMAP: <leader>ai
			vim.keymap.set(
				{ "n", "v" },
				"<leader>ai",
				"<cmd>TransformCode<cr>",
				{ desc = "Transform code using ai.nvim." }
			)
		end,
	},
}
