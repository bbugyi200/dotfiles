if require("funcs").on_google_machine() then
	local glug = require("glug").glug
	return {
		-- maktaba is required by all google plugins
		glug("maktaba", {
			lazy = true,
			dependencies = {},
			config = function()
				vim.cmd("source /usr/share/vim/google/glug/bootstrap.vim")
			end,
		}),
		glug("relatedfiles", {
			cmd = "RelatedFilesWindow",
			keys = {
				{
					"<leader>sx",
					"<cmd>RelatedFilesWindow<cr>",
					desc = "Show related files",
				},
			},
		}),
		{
			url = "sso://user/vvvv/ai.nvim",
			dependencies = {
				"nvim-lua/plenary.nvim",
			},
			cmd = "TransformCode",
			keys = {
				{ "<leader>tc", "<cmd>TransformCode<cr>", mode = { "n", "v" }, desc = "Transform code" },
			},
		},
	}
else
	return {}
end
