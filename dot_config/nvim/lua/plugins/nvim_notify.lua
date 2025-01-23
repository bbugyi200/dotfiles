return {
	-- PLUGIN: http://github.com/rcarriga/nvim-notify
	{
		"rcarriga/nvim-notify",
		init = function()
			vim.notify = require("notify")
		end,
	},
}
