return {
	"mbbill/undotree",
	init = function()
		-- KEYMAP(N): <leader>u
		vim.keymap.set("n", "<leader>u", vim.cmd.UndotreeToggle, { desc = "Map to activate/deactivate undotree." })
		vim.g.undotree_SetFocusWhenToggle = 1
		vim.g.undotree_WindowLayout = 4
		vim.g.undotree_DiffpanelHeight = 15
	end,
}
