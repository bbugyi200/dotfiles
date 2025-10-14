--- CodeCompanion /paths slash command.
---
--- Allows users to input one or more filepaths (separated by whitespace)
--- and adds those files to the chat context.

return {
	keymaps = {
		modes = { i = "<c-g>,", n = "g," },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		-- Prompt user for filepaths
		vim.ui.input({
			prompt = "Enter filepaths (separated by whitespace): ",
			default = "",
		}, function(input)
			if not input or vim.trim(input) == "" then
				vim.notify("No filepaths provided", vim.log.levels.WARN)
				return
			end

			-- Split input by whitespace to get individual filepaths
			local filepaths = {}
			for filepath in input:gmatch("%S+") do
				table.insert(filepaths, filepath)
			end

			if #filepaths == 0 then
				vim.notify("No valid filepaths found", vim.log.levels.WARN)
				return
			end

			local added_count = 0
			local failed_files = {}

			-- Process each filepath
			for _, filepath in ipairs(filepaths) do
				-- Expand path (handle ~ and environment variables)
				local expanded_path = vim.fn.expand(filepath)

				-- Convert relative paths to absolute paths based on cwd
				if not vim.startswith(expanded_path, "/") then
					expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
				end

				if vim.fn.filereadable(expanded_path) == 1 then
					-- Read the file content
					local content = table.concat(vim.fn.readfile(expanded_path), "\n")
					local relative_path = vim.fn.fnamemodify(expanded_path, ":~")
					local ft = vim.fn.fnamemodify(expanded_path, ":e")
					local id = "<file>" .. relative_path .. "</file>"

					-- Add the file as a message to the chat
					---@diagnostic disable-next-line: undefined-field
					chat:add_message({
						role = "user",
						content = string.format(
							"Here is the content from a file (including line numbers):\n```%s\n%s:%s\n%s\n```",
							ft,
							relative_path,
							relative_path,
							content
						),
					}, {
						path = expanded_path,
						context_id = id,
						tag = "file",
						visible = false,
					})

					-- Add to context tracking
					---@diagnostic disable-next-line: undefined-field
					chat.context:add({
						id = id,
						path = expanded_path,
						source = "codecompanion.strategies.chat.slash_commands.paths",
					})

					added_count = added_count + 1
				else
					table.insert(failed_files, filepath)
				end
			end

			-- Provide feedback to user
			if added_count > 0 then
				vim.notify(string.format("Added %d files to chat context", added_count), vim.log.levels.INFO)
			end

			if #failed_files > 0 then
				vim.notify(
					string.format("Failed to read %d files: %s", #failed_files, table.concat(failed_files, ", ")),
					vim.log.levels.WARN
				)
			end
		end)
	end,
	description = "Add multiple files to context by entering filepaths separated by whitespace",
	opts = {
		contains_code = true,
	},
}
