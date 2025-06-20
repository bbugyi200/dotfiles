--- CodeCompanion group management slash commands.
---
--- Allows users to save and load collections of references from chat contexts.

local groups_dir = vim.fn.expand("~/tmp/cc_groups")

--- Ensure the groups directory exists
local function ensure_groups_dir()
	vim.fn.mkdir(groups_dir, "p")
end

--- Save current chat references to a group file
local function save_group(chat)
	vim.ui.input({
		prompt = "Group name: ",
		default = "",
	}, function(group_name)
		if not group_name or group_name == "" then
			vim.notify("No group name provided", vim.log.levels.WARN)
			return
		end

		ensure_groups_dir()

		-- Get current references from chat
		local refs = chat.refs or {}
		if vim.tbl_isempty(refs) then
			vim.notify("No references found in current chat", vim.log.levels.WARN)
			return
		end

		-- Prepare data to save
		local group_data = {
			name = group_name,
			created_at = os.date("%Y-%m-%d %H:%M:%S"),
			references = {},
		}

		-- Process each reference
		for _, ref in pairs(refs) do
			-- Normalize source to simple identifiers
			local normalized_source = ref.source
			if ref.source:find("file") then
				normalized_source = "file"
			elseif ref.source:find("buffer") then
				normalized_source = "buffer"
			end

			local ref_data = {
				source = normalized_source,
				id = ref.id,
				opts = ref.opts,
			}

			-- Extract file path from ID if it's in XML format
			if ref.id and ref.id:match("^<file>(.+)</file>$") then
				ref_data.file_path = ref.id:match("^<file>(.+)</file>$")
			end

			-- For buffer references, try to get the content
			if ref.bufnr then
				ref_data.bufnr = ref.bufnr
				local buf_name = vim.api.nvim_buf_get_name(ref.bufnr)
				if buf_name and buf_name ~= "" then
					ref_data.file_path = vim.fn.fnamemodify(buf_name, ":~")
				end
			end

			table.insert(group_data.references, ref_data)
		end

		-- Save to file
		local filename = group_name:gsub("[^%w%-_]", "_") .. ".json"
		local filepath = groups_dir .. "/" .. filename

		local file = io.open(filepath, "w")
		if file then
			file:write(vim.json.encode(group_data))
			file:close()
			vim.notify(
				string.format("Saved %d references to group '%s'", #group_data.references, group_name),
				vim.log.levels.INFO
			)
		else
			vim.notify("Failed to save group file: " .. filepath, vim.log.levels.ERROR)
		end
	end)
end

--- Load references from a group file
local function load_group(chat)
	ensure_groups_dir()

	-- Get all group files
	local group_files = vim.fn.globpath(groups_dir, "*.json", false, true)

	if #group_files == 0 then
		vim.notify("No saved groups found in " .. groups_dir, vim.log.levels.WARN)
		return
	end

	-- Prepare options for selection
	local options = {}
	local file_map = {}

	for _, filepath in ipairs(group_files) do
		local file = io.open(filepath, "r")
		if file then
			local content = file:read("*all")
			file:close()

			local ok, group_data = pcall(vim.json.decode, content)
			if ok and group_data.name then
				local display_name = string.format(
					"%s (%d refs, %s)",
					group_data.name,
					#(group_data.references or {}),
					group_data.created_at or "unknown date"
				)
				table.insert(options, display_name)
				file_map[display_name] = filepath
			end
		end
	end

	if #options == 0 then
		vim.notify("No valid group files found", vim.log.levels.WARN)
		return
	end

	-- Let user select a group
	vim.ui.select(options, {
		prompt = "Select group to load:",
	}, function(selected)
		if not selected then
			return
		end

		local filepath = file_map[selected]
		local file = io.open(filepath, "r")
		if not file then
			vim.notify("Failed to read group file", vim.log.levels.ERROR)
			return
		end

		local content = file:read("*all")
		file:close()

		local ok, group_data = pcall(vim.json.decode, content)
		if not ok then
			vim.notify("Failed to parse group file", vim.log.levels.ERROR)
			return
		end

		local loaded_count = 0
		for _, ref_data in ipairs(group_data.references or {}) do
			if ref_data.file_path then
				-- Try to load file or buffer reference using file path
				local expanded_path = vim.fn.expand(ref_data.file_path)
				if vim.fn.filereadable(expanded_path) == 1 then
					local file_content = table.concat(vim.fn.readfile(expanded_path), "\n")
					local ext = vim.fn.fnamemodify(expanded_path, ":e")

					-- Use appropriate label based on source
					local label = ref_data.source == "buffer" and "Buffer" or "File"
					chat:add_reference({
						role = "user",
						content = string.format(
							"%s: %s\n\n```%s\n%s\n```",
							label,
							ref_data.file_path,
							ext,
							file_content
						),
					}, ref_data.source, ref_data.id)
					loaded_count = loaded_count + 1
				else
					vim.notify("File not found: " .. ref_data.file_path, vim.log.levels.WARN)
				end
			else
				vim.notify("No file path found for reference: " .. (ref_data.id or "unknown"), vim.log.levels.WARN)
			end
		end

		vim.notify(
			string.format("Loaded %d references from group '%s'", loaded_count, group_data.name),
			vim.log.levels.INFO
		)
	end)
end

return {
	save_group = {
		keymaps = {
			modes = { i = "<c-g>S", n = "gS" },
		},
		callback = save_group,
		description = "Save current chat references to a named group",
		opts = {
			contains_code = false,
		},
	},
	load_group = {
		keymaps = {
			modes = { i = "<c-g>l", n = "gl" },
		},
		callback = load_group,
		description = "Load references from a saved group",
		opts = {
			contains_code = true,
		},
	},
}
