--- A task runner and job management plugin for Neovim.

--- Checks if the current working directory contains a 'targets.mk' file with a 'lint-and-test' target.
---
--- This function reads the 'targets.mk' file in the current working directory and searches
--- for a target named 'lint-and-test:'. It can be used to determine if a project has a
--- standardized linting and testing make target.
---
---@return boolean # Returns true if a 'lint-and-test' target is found, false otherwise
local function has_lint_and_test_target()
	local cwd = vim.fn.getcwd()
	local targets_mk_path = cwd .. "/targets.mk"

	if vim.fn.filereadable(targets_mk_path) == 1 then
		local content = vim.fn.readfile(targets_mk_path)
		for _, line in ipairs(content) do
			if line:match("^lint%-and%-test:") then
				return true
			end
		end
	end

	return false
end

return {
	-- PLUGIN: http://github.com/stevearc/overseer.nvim
	{
		"stevearc/overseer.nvim",
		opts = {
			strategy = { "toggleterm", direction = "float" },
			templates = { "builtin", "make_targets" },
		},
		init = function()
			-- KEYMAP GROUP: <leader>o
			vim.keymap.set("n", "<leader>o", "<nop>", { desc = "overseer.nvim" })

			-- KEYMAP: <leader>or
			vim.keymap.set("n", "<leader>or", "<cmd>OverseerRun<cr>", { desc = "OverseerRun" })

			if has_lint_and_test_target() then
				vim.keymap.set(
					"n",
					"<leader>oR",
					"<cmd>OverseerRunCmd make lint-and-test<cr>",
					{ desc = "OverseerRunCmd make lint-and-test" }
				)
			end

			-- KEYMAP: <leader>ot
			vim.keymap.set("n", "<leader>ot", "<cmd>OverseerToggle<cr>", { desc = "OverseerToggle" })
		end,
	},
}
