--- Provides :TransformCode command that lets LLMs modify current file/selection.

-- PLUGIN: http://go/ai.nvim
return {
	{
		url = "sso://user/vvvv/ai.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
		},
		cmd = "TransformCode",
		keys = {
			-- KEYMAP: <leader>ai
			{
				"<leader>ai",
				"<cmd>TransformCode<cr>",
				mode = { "n", "v" },
				desc = "Transform code using ai.nvim.",
			},
		},
	},
}
