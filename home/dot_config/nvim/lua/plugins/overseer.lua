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

			-- KEYMAP GROUP: <leader>or
			vim.keymap.set("n", "<leader>or", "<nop>", { desc = "OverseerRun" })

			if has_make_target("lint-and-test") then
				-- KEYMAP: <leader>ora
				vim.keymap.set(
					"n",
					"<leader>ora",
					"<cmd>OverseerRunCmd make lint-and-test<cr>",
					{ desc = "OverseerRunCmd make lint-and-test" }
				)
			elseif has_make_target("all") then
				-- KEYMAP: <leader>ora
				vim.keymap.set(
					"n",
					"<leader>ora",
					"<cmd>OverseerRunCmd make all<cr>",
					{ desc = "OverseerRunCmd make all" }
				)
			end

			if has_make_target("lint") then
				-- KEYMAP: <leader>orl
				vim.keymap.set(
					"n",
					"<leader>orl",
					"<cmd>OverseerRunCmd make lint<cr>",
					{ desc = "OverseerRunCmd make lint" }
				)
			end

			if has_make_target("test") then
				-- KEYMAP: <leader>ort
				vim.keymap.set(
					"n",
					"<leader>ort",
					"<cmd>OverseerRunCmd make test<cr>",
					{ desc = "OverseerRunCmd make test" }
				)
			end

			-- KEYMAP: <leader>orr
			vim.keymap.set("n", "<leader>orr", "<cmd>OverseerRun<cr>", { desc = "OverseerRun" })

			-- KEYMAP: <leader>ot
			vim.keymap.set("n", "<leader>ot", "<cmd>OverseerToggle<cr>", { desc = "OverseerToggle" })
		end,
	},
}
