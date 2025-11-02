--- Run a command that outputs file paths and present them via Telescope.
---
--- This function executes the given command, expects newline-separated file paths as output,
--- and presents them in a Telescope picker. Selected files are opened for editing.
---
---@param command_name string The shell command to execute (e.g., "find . -name '*.txt'")
---@param opts? table Optional Telescope picker options
local function telescope_command_files(command_name, opts)
	local pickers = require("telescope.pickers")
	local finders = require("telescope.finders")
	local conf = require("telescope.config").values
	local actions = require("telescope.actions")
	local action_state = require("telescope.actions.state")

	opts = opts or {}

	-- Execute the command and capture output
	local handle = io.popen(command_name .. " 2>/dev/null")
	if not handle then
		vim.notify("Failed to execute command: " .. command_name, vim.log.levels.ERROR)
		return
	end

	local output = handle:read("*a")
	local exit_code = handle:close()

	if not exit_code then
		vim.notify("Command failed: " .. command_name, vim.log.levels.ERROR)
		return
	end

	-- Split output into lines and filter out empty lines
	local files = {}
	for line in output:gmatch("[^\r\n]+") do
		if line:match("%S") then -- Only add non-empty lines
			table.insert(files, line)
		end
	end

	if #files == 0 then
		vim.notify("No files found from command: " .. command_name, vim.log.levels.WARN)
		return
	end

	-- Custom action to open selected files
	local function open_selected_files(prompt_bufnr)
		local picker = action_state.get_current_picker(prompt_bufnr)
		local selections = picker:get_multi_selection()

		actions.close(prompt_bufnr)

		-- If no multi-selections, use the current selection
		if vim.tbl_isempty(selections) then
			local current_selection = action_state.get_selected_entry()
			if current_selection then
				vim.cmd("edit " .. vim.fn.fnameescape(current_selection.value))
			end
		else
			-- Open all multi-selections
			for _, selection in ipairs(selections) do
				vim.cmd("edit " .. vim.fn.fnameescape(selection.value))
			end
		end
	end

	-- Create and run the picker
	pickers
		.new(opts, {
			prompt_title = opts.prompt_title or ("Command Results: " .. command_name),
			finder = finders.new_table({
				results = files,
			}),
			sorter = conf.generic_sorter(opts),
			previewer = conf.file_previewer(opts),
			attach_mappings = function(_, map)
				-- Override default select action
				actions.select_default:replace(open_selected_files)

				-- Optional: add explicit mapping
				map("i", "<C-m>", open_selected_files)
				map("n", "<CR>", open_selected_files)

				return true
			end,
		})
		:find()
end

return telescope_command_files
