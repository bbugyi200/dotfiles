--- Revolutionize Your Neovim Tab Workflow: Introducing Enhanced Tab Scoping!

return {
	-- PLUGIN: http://github.com/tiagovla/scope.nvim
	{
		"tiagovla/scope.nvim",
		opts = {},
		init = function()
			-- KEYMAP: <leader>tB
			vim.keymap.set("n", "<leader>tB", "<cmd>Telescope scope buffers<cr>", {
				desc = "Telescope scope buffers",
			})
		end,
	},
}
