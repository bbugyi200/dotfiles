--- CodeCompanion /cs slash command,
---
--- Allows users to search for files using the telescope-codesearch extension
--- and add them to the chat context.

local shared = require("plugins.codecompanion.slash_cmds.shared")

return {
	keymaps = {
		modes = { i = "<c-g>cs", n = "gcs" },
	},
	callback = function(chat)
		-- Check if telescope-codesearch is available
		local telescope = require("telescope")
		if not telescope.extensions.codesearch then
			vim.notify("telescope-codesearch extension not found", vim.log.levels.ERROR)
			return
		end

		local picker_opts = {
			attach_mappings = function(prompt_bufnr, map)
				local actions = require("telescope.actions")
				local action_state = require("telescope.actions.state")

				actions.select_default:replace(function()
					local paths = shared.get_selected_paths(prompt_bufnr)
					actions.close(prompt_bufnr)

					if #paths > 0 then
						shared.add_files_to_chat(paths, chat, "cs")
					else
						vim.notify("No files selected", vim.log.levels.WARN)
					end
				end)

				-- Setup common keymaps using shared utility
				shared.setup_common_keymaps(map, actions)

				return true
			end,
			-- Add some useful codesearch options
			experimental = true, -- Include experimental directory
			enable_proximity = true, -- Enable proximity search
			max_num_results = 100, -- Increase max results
		}

		telescope.extensions.codesearch.find_query(picker_opts)
	end,
	description = "Add files from CodeSearch to context",
	opts = {
		contains_code = true,
	},
}
