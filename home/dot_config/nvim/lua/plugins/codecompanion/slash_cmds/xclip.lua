--- CodeCompanion /xclip slash command.
---
--- Prompts user for a filename prefix, creates a file in the current working directory named <prefix>_$(hcn).txt
--- where $(hcn) is replaced with the output of the hcn shell command if available,
--- otherwise creates <prefix>.txt, and writes the current clipboard contents to the file.

return {
	keymaps = {
		modes = { i = "<c-g>X", n = "gX" },
	},
	callback = function(chat)
		-- Prompt user for filename prefix
		vim.ui.input({
			prompt = "Filename (with optional extension, defaults to .txt): ",
			default = "",
		}, function(prefix)
			if not prefix or prefix == "" then
				vim.notify("No prefix provided", vim.log.levels.WARN)
				return
			end

			-- Check if hcn command exists
			local hcn_suffix = ""
			if vim.fn.executable("hcn") == 1 then
				-- Execute the hcn command
				local hcn_handle = io.popen("hcn")
				if not hcn_handle then
					vim.notify("Failed to execute hcn command", vim.log.levels.ERROR)
					return
				end

				local hcn_output = hcn_handle:read("*all")
				hcn_handle:close()

				-- Clean up the hcn output (remove trailing newlines/whitespace)
				hcn_output = vim.trim(hcn_output)

				if hcn_output == "" then
					vim.notify("hcn command returned empty output", vim.log.levels.WARN)
				else
					hcn_suffix = "_" .. hcn_output
				end
			end

			-- Get clipboard contents
			local clipboard_cmd
			if vim.fn.has("mac") == 1 then
				clipboard_cmd = "pbpaste"
			else
				clipboard_cmd = "xclip -o -sel clipboard"
			end

			local clipboard_handle = io.popen(clipboard_cmd)
			if not clipboard_handle then
				vim.notify("Failed to execute clipboard command: " .. clipboard_cmd, vim.log.levels.ERROR)
				return
			end

			local clipboard_content = clipboard_handle:read("*all")
			clipboard_handle:close()

			-- Create the filename, checking if prefix already has an extension
			local filename
			local extension_match = prefix:match("%.(%w+)$")
			if extension_match then
				-- Prefix has an extension, insert hcn_suffix before the extension
				local basename = prefix:match("(.+)%.%w+$")
				filename = basename .. hcn_suffix .. "." .. extension_match
			else
				-- No extension, add hcn_suffix and .txt
				filename = prefix .. hcn_suffix .. ".txt"
			end

			-- Create a file in the current working directory
			local output_file = vim.fn.getcwd() .. "/" .. filename

			local file = io.open(output_file, "w")
			if not file then
				vim.notify("Failed to create file: " .. output_file, vim.log.levels.ERROR)
				return
			end

			-- Write content to the file
			local timestamp = os.date("%Y-%m-%d %H:%M:%S")
			file:write(string.format("# File: %s\n", filename))
			file:write(string.format("# Created: %s\n", timestamp))
			file:write(string.format("# Clipboard command: %s\n\n", clipboard_cmd))

			-- Write the clipboard content
			if clipboard_content and clipboard_content ~= "" then
				file:write(clipboard_content)
				-- Ensure file ends with a newline if clipboard content doesn't
				if not vim.endswith(clipboard_content, "\n") then
					file:write("\n")
				end
			else
				file:write("-- Clipboard was empty --\n")
			end

			file:close()

			-- Read the file content and add to chat context
			local content = table.concat(vim.fn.readfile(output_file), "\n")
			local relative_path = vim.fn.fnamemodify(output_file, ":~")
			local ft = vim.fn.fnamemodify(output_file, ":e")
			local id = "<file>" .. relative_path .. "</file>"

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
				path = output_file,
				context_id = id,
				tag = "file",
				visible = false,
			})

			-- Add to context tracking
			chat.context:add({
				id = id,
				path = output_file,
				source = "codecompanion.strategies.chat.slash_commands.xclip",
			})

			vim.notify(
				string.format("Created %s with clipboard contents and added to chat context", filename),
				vim.log.levels.INFO
			)
		end)
	end,
	description = "Create a file with clipboard contents using <prefix>_$(hcn).txt format (or"
		.. " <prefix>.txt if hcn unavailable)",
}
