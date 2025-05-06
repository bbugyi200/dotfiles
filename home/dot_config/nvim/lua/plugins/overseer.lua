--- A task runner and job management plugin for Neovim.

--- Checks if the current working directory contains a target in a 'targets.mk' file.
---
---@param target string The name of the make target to search for
---@return boolean # Returns true if the target is found, false otherwise
local function has_make_target(target)
	local cwd = vim.fn.getcwd()
	local targets_mk_path = cwd .. "/targets.mk"

	if vim.fn.filereadable(targets_mk_path) == 1 then
		local content = vim.fn.readfile(targets_mk_path)
		for _, line in ipairs(content) do
			if line:match("^" .. target:gsub("%-", "%%-") .. ":") then
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

			local has_lint_target = has_make_target("lint")
			if has_lint_target then
				-- KEYMAP: <leader>orl
				vim.keymap.set(
					"n",
					"<leader>orl",
					"<cmd>OverseerRunCmd make lint<cr>",
					{ desc = "OverseerRunCmd make lint" }
				)
			end

			local has_test_target = has_make_target("test")
			if has_test_target then
				-- KEYMAP: <leader>ort
				vim.keymap.set(
					"n",
					"<leader>ort",
					"<cmd>OverseerRunCmd make test<cr>",
					{ desc = "OverseerRunCmd make test" }
				)
			end

			if has_lint_target and has_test_target then
				-- KEYMAP: <leader>ora
				vim.keymap.set(
					"n",
					"<leader>ora",
					"<cmd>OverseerRunCmd make lint && make test<cr>",
					{ desc = "OverseerRunCmd make lint && make test" }
				)
			end

			if has_lint_target or has_test_target then
				-- KEYMAP GROUP: <leader>or
				vim.keymap.set("n", "<leader>or", "<nop>", { desc = "OverseerRun" })
				-- KEYMAP: <leader>orr
				vim.keymap.set("n", "<leader>orr", "<cmd>OverseerRun<cr>", { desc = "OverseerRun" })
			else
				-- KEYMAP: <leader>or
				vim.keymap.set("n", "<leader>or", "<cmd>OverseerRun<cr>", { desc = "OverseerRun" })
			end

			-- KEYMAP: <leader>ot
			vim.keymap.set("n", "<leader>ot", "<cmd>OverseerToggle<cr>", { desc = "OverseerToggle" })
		end,
	},
}
