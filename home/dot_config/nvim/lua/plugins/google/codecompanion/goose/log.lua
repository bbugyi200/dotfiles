local M = {}

local log_file = vim.fn.stdpath("cache") .. "/codecompanion-goose.log"
local debug_enabled = false

--- Setup logging
---@param debug boolean Whether to enable debug logging
function M.setup(debug)
	debug_enabled = debug
end

--- Log a debug message
---@param message string The message to log
function M.debug(message)
	if debug_enabled then
		local timestamp = os.date("%Y-%m-%d %H:%M:%S")
		local log_line = string.format("[%s] DEBUG: %s\n", timestamp, message)

		local file = io.open(log_file, "a")
		if file then
			file:write(log_line)
			file:close()
		end

		print("[CodeCompanion-Goose DEBUG] " .. message)
	end
end

--- Log an info message
---@param message string The message to log
function M.info(message)
	local timestamp = os.date("%Y-%m-%d %H:%M:%S")
	local log_line = string.format("[%s] INFO: %s\n", timestamp, message)

	local file = io.open(log_file, "a")
	if file then
		file:write(log_line)
		file:close()
	end

	if debug_enabled then
		print("[CodeCompanion-Goose INFO] " .. message)
	end
end

--- Log a warning message
---@param message string The message to log
function M.warning(message)
	local timestamp = os.date("%Y-%m-%d %H:%M:%S")
	local log_line = string.format("[%s] WARNING: %s\n", timestamp, message)

	local file = io.open(log_file, "a")
	if file then
		file:write(log_line)
		file:close()
	end

	print("[CodeCompanion-Goose WARNING] " .. message)
end

--- Log an error message
---@param message string The message to log
---@param ... any Additional arguments for string formatting
function M.error(message, ...)
	local formatted_message = string.format(message, ...)
	local timestamp = os.date("%Y-%m-%d %H:%M:%S")
	local log_line = string.format("[%s] ERROR: %s\n", timestamp, formatted_message)

	local file = io.open(log_file, "a")
	if file then
		file:write(log_line)
		file:close()
	end

	vim.notify("[CodeCompanion-Goose ERROR] " .. formatted_message, vim.log.levels.ERROR)
end

return M

