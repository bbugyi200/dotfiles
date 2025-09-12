-- filepath: ~/.local/share/chezmoi/home/dot_config/nvim/lua/plugins/codecompanion/slash_cmds/xclip.lua
--- CodeCompanion /xclip slash command.
---
--- Prompts user for a filename prefix and creates a temporary file named <prefix>_$(hcn).txt
--- where $(hcn) is replaced with the output of the hcn shell command.

return {
	keymaps = {
		modes = { i = "<c-l>", n = "gL" },
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

			-- Execute the hcn command
			local handle = io.popen("hcn")
			if not handle then
				vim.notify("Failed to execute hcn command", vim.log.levels.ERROR)
				return
			end

			local hcn_output = handle:read("*all")
			handle:close()

			-- Clean up the hcn output (remove trailing newlines/whitespace)
			hcn_output = vim.trim(hcn_output)

			if hcn_output == "" then
				vim.notify("hcn command returned empty output", vim.log.levels.WARN)
				return
			end

			-- Create the filename
			local filename = prefix .. "_" .. hcn_output .. ".txt"

			-- Create a temporary file
			local temp_dir = vim.fn.fnamemodify(vim.fn.tempname(), ":h")
			local temp_file = temp_dir .. "/" .. filename

			local file = io.open(temp_file, "w")
			if not file then
				vim.notify("Failed to create temporary file: " .. temp_file, vim.log.levels.ERROR)
				return
			end

			-- Write initial content to the file
			local timestamp = os.date("%Y-%m-%d %H:%M:%S")
			file:write(string.format("# File: %s\n", filename))
			file:write(string.format("# Created: %s\n", timestamp))
			file:write(string.format("# Prefix: %s\n", prefix))
			file:write(string.format("# HCN: %s\n\n", hcn_output))
			file:write("-- Add your content here --\n")
			file:close()

			-- Read the file content and add to chat context
			local content = table.concat(vim.fn.readfile(temp_file), "\n")
			chat:add_context({
				role = "user",
				content = string.format("File: %s\n\n```txt\n%s\n```", filename, content),
			}, "file", temp_file)

			vim.notify("Created and added " .. filename .. " to chat context", vim.log.levels.INFO)
		end)
	end,
	description = "Create a temporary file with <prefix>_$(hcn).txt format and add to context",
}
