--- CodeCompanion /xclip slash command.
---
--- Prompts user for a filename prefix, creates a temporary file named <prefix>_$(hcn).txt
--- where $(hcn) is replaced with the output of the hcn shell command if available,
--- otherwise creates <prefix>.txt, and writes the current clipboard contents to the file.

return {
	keymaps = {
		modes = { i = "<c-g>X", n = "gX" },
	},
	callback = function(chat)
		-- Prompt user for filename prefix
		vim.ui.input({
			prompt = "File prefix: ",
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
					return
				end

				hcn_suffix = "_" .. hcn_output
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
			if prefix:match("%.%w+$") then
				-- Prefix already has an extension, use it as-is
				filename = prefix .. hcn_suffix
			else
				-- No extension, add .txt
				filename = prefix .. hcn_suffix .. ".txt"
			end

			-- Create a temporary file
			local temp_dir = vim.fn.fnamemodify(vim.fn.tempname(), ":h")
			local temp_file = temp_dir .. "/" .. filename

			local file = io.open(temp_file, "w")
			if not file then
				vim.notify("Failed to create temporary file: " .. temp_file, vim.log.levels.ERROR)
				return
			end

			-- Write content to the file
			local timestamp = os.date("%Y-%m-%d %H:%M:%S")
			file:write(string.format("### File: %s\n", filename))
			file:write(string.format("### Created: %s\n", timestamp))
			file:write(string.format("### Clipboard command: %s\n\n", clipboard_cmd))

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
			local content = table.concat(vim.fn.readfile(temp_file), "\n")
			chat:add_context({
				role = "user",
				content = string.format("File: %s\n\n```txt\n%s\n```", filename, content),
			}, "file", temp_file)

			vim.notify(
				string.format("Created %s with clipboard contents and added to chat context", filename),
				vim.log.levels.INFO
			)
		end)
	end,
	description = "Create a temporary file with clipboard contents using <prefix>_$(hcn).txt format (or <prefix>.txt if hcn unavailable)",
}
