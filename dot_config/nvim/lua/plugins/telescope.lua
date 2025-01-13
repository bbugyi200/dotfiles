-- P0: Install Telescope extensions!
--   [ ] Find alternative to `:Telescope buffers` that favors most recent buffers.
--   [ ] Install extension for CodeSearch.
--   [ ] Use ,t<L> maps with Telescope builtins and extensions!
return {
	"nvim-telescope/telescope.nvim",
	branch = "0.1.x",
	dependencies = { "nvim-lua/plenary.nvim" },
	opts = {},
	init = function()
		local builtin = require("telescope.builtin")
		vim.keymap.set("n", "<space>", builtin.buffers, { desc = "Telescope buffers" })
		vim.keymap.set("n", "<leader>tb", builtin.buffers, { desc = "Telescope buffers" })
		vim.keymap.set("n", "<leader>tf", builtin.find_files, { desc = "Telescope find files" })
		vim.keymap.set("n", "<leader>tg", builtin.live_grep, { desc = "Telescope live grep" })
		vim.keymap.set("n", "<leader>th", builtin.help_tags, { desc = "Telescope help tags" })
	end,
}
