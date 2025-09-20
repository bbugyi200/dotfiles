--- CodeCompanion /xref slash command.
---
--- Allows users to find references to a symbol using the xref_files script.
--- The symbol can be provided as input or defaults to clipboard contents.
--- All files containing references to the symbol are added to the chat context.

return {
	keymaps = {
		modes = { i = "<c-g>xr", n = "gxr" },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		-- Get clipboard contents as default
		local clipboard_cmd
		if vim.fn.has("mac") == 1 then
			clipboard_cmd = "pbpaste"
		else
			clipboard_cmd = "xclip -o -sel clipboard"
		end

		local clipboard_handle = io.popen(clipboard_cmd)
		local default_symbol = ""
		if clipboard_handle then
			local clipboard_content = clipboard_handle:read("*all")
			clipboard_handle:close()
			if clipboard_content then
				default_symbol = vim.trim(clipboard_content)
			end
		end

		-- Prompt user for symbol (with clipboard as default)
		vim.ui.input({
			prompt = "Symbol to find references for: ",
			default = default_symbol,
		}, function(symbol)
			if not symbol or vim.trim(symbol) == "" then
				vim.notify("No symbol provided", vim.log.levels.WARN)
				return
			end

			symbol = vim.trim(symbol)

			-- Check if xref_files command exists
			if vim.fn.executable("xref_files") ~= 1 then
				vim.notify("xref_files command not found in PATH", vim.log.levels.ERROR)
				return
			end

			-- Run xref_files command with the symbol
			local cmd = { "xref_files", symbol }
			---@diagnostic disable-next-line: missing-fields
			local job = require("plenary.job"):new({
				command = cmd[1],
				args = { cmd[2] },
				on_exit = function(j, return_val)
					if return_val == 0 then
						local stdout = j:result()
						local stderr = j:stderr_result()
						local stderr_content = table.concat(stderr, "\n")

						if stderr_content and stderr_content ~= "" then
							vim.notify("STDERR: " .. stderr_content, vim.log.levels.WARN)
						end

						-- Parse file paths from stdout
						local file_paths = {}
						for _, line in ipairs(stdout) do
							local trimmed = vim.trim(line)
							if trimmed ~= "" and vim.fn.filereadable(trimmed) == 1 then
								table.insert(file_paths, trimmed)
							end
						end

						if #file_paths == 0 then
							vim.schedule(function()
								vim.notify("No readable files found for symbol: " .. symbol, vim.log.levels.WARN)
							end)
							return
						end

						-- Schedule the file operations for the main event loop
						vim.schedule(function()
							-- Add each file to the chat context
							local added_count = 0
							for _, path in ipairs(file_paths) do
								if vim.fn.filereadable(path) == 1 then
									-- Read the file content
									local content = table.concat(vim.fn.readfile(path), "\n")
									local relative_path = vim.fn.fnamemodify(path, ":~")
									local ft = vim.fn.fnamemodify(path, ":e")
									local id = "<file>" .. relative_path .. "</file>"

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
										path = path,
										context_id = id,
										tag = "file",
										visible = false,
									})

									-- Add to context tracking
									---@diagnostic disable-next-line: undefined-field
									chat.context:add({
										id = id,
										path = path,
										source = "codecompanion.strategies.chat.slash_commands.xrefs",
									})

									added_count = added_count + 1
								else
									vim.notify("File not readable: " .. path, vim.log.levels.WARN)
								end
							end

							if added_count > 0 then
								vim.notify(
									string.format(
										"Added %d files containing references to '%s' to chat context",
										added_count,
										symbol
									),
									vim.log.levels.INFO
								)
							end
						end)
					else
						local stderr = j:stderr_result()
						local error_msg = table.concat(stderr, "\n")
						vim.schedule(function()
							vim.notify("xref_files command failed: " .. error_msg, vim.log.levels.ERROR)
						end)
					end
				end,
			})

			job:start()
		end)
	end,
	description = "Find files containing references to a symbol using xref_files and add them to context",
	opts = {
		contains_code = true,
	},
}
