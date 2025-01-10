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
	}
else
	return {}
end
