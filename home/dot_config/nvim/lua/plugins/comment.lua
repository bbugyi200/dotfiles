return {
	-- PLUGIN: http://github.com/numToStr/Comment.nvim
	{
		"numToStr/Comment.nvim",
		opts = {},
		init = function()
			-- Configure SCSS files to use line comments instead of block comments
			local ft = require("Comment.ft")
			ft.set("scss", "// %s")
		end,
	},
}
