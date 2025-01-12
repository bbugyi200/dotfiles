-- P1: Telescope extensions
--   [ ] Install lots of Telescope extensions!
--   [ ] Use ,t<L> maps with Telescope builtins and extensions!
--   [ ] Find alternative to `:Telescope buffers` that favors most recent buffers.
return {
	"nvim-telescope/telescope.nvim",
	branch = "0.1.x",
	dependencies = { "nvim-lua/plenary.nvim" },
	init = function()
		local builtin = require("telescope.builtin")
		vim.keymap.set("n", "<space>", builtin.buffers, { desc = "Telescope buffers" })
		vim.keymap.set("n", "<leader>fb", builtin.buffers, { desc = "Telescope buffers" })
		vim.keymap.set("n", "<leader>ff", builtin.find_files, { desc = "Telescope find files" })
		vim.keymap.set("n", "<leader>fg", builtin.live_grep, { desc = "Telescope live grep" })
		vim.keymap.set("n", "<leader>fh", builtin.help_tags, { desc = "Telescope help tags" })
		require("telescope").setup({})
	end,
}
