--- CodeCompanion /local slash command.
---
--- Allows users to select files from configured local directories
--- and add them to the chat context.

local shared = require("plugins.codecompanion.slash_cmds.shared")

local cwd = vim.fn.getcwd()
local fav_dirs = { vim.fn.expand("~/bb"), cwd .. "/bb", cwd .. "/xcmds", cwd .. "/xclips" }
local allowed_exts = { "json", "md", "sql", "txt", "xml" }
local excluded_dirs = {}

return {
	keymaps = {
		modes = { i = "<c-f>", n = "gf" },
	},
	callback = function(chat)
		-- Collect all files from configured directories
		local all_files = {}

		for _, dir in ipairs(fav_dirs) do
			if vim.fn.isdirectory(dir) == 1 then
				-- Get files from this directory recursively.
				local files = vim.fn.globpath(dir, "**/*", false, true)
				for _, file in ipairs(files) do
					if vim.fn.filereadable(file) == 1 then
						-- Check if file is in an excluded directory
						local is_excluded = false
						for _, excluded_dir in ipairs(excluded_dirs) do
							if vim.startswith(file, excluded_dir) then
								is_excluded = true
								break
							end
						end

						if is_excluded then
							goto continue
						end

						-- Check if file has an allowed extension
						local ext = vim.fn.fnamemodify(file, ":e")
						local has_allowed_ext = false
						for _, allowed_ext in ipairs(allowed_exts) do
							if ext == allowed_ext then
								has_allowed_ext = true
								break
							end
						end

						if has_allowed_ext then
							table.insert(all_files, file)
						end
						::continue::
					end
				end
			end
		end

		if #all_files == 0 then
			vim.notify("No readable files found in configured directories", vim.log.levels.WARN)
			return
		end

		-- Use shared file picker
		local title = string.format("Favorite Files (%d files)", #all_files)
		shared.create_file_picker(title, all_files, chat, "favs", {
			show_preview = true,
		})
	end,
	description = "Add files from configured local directories to context",
}
