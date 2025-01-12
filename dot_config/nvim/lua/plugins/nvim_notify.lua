-- P1: Use `vim.notify` from all [[zorg]] [[vim]] functions?!
return {
	"rcarriga/nvim-notify",
	init = function()
		vim.notify = require("notify")
	end,
}
