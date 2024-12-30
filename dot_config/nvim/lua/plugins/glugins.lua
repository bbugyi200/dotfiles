local funcs = require("funcs")
local glug = require("glug")

if funcs.on_google_machine() then
	return {
		glug.glug("relatedfiles", {
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
