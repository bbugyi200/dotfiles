local is_goog_machine = require("bb_utils.is_goog_machine")

if not is_goog_machine() then
	return {}
end

-- Get the directory of the current file
---@diagnostic disable-next-line: undefined-field
local this_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
this_dir = this_dir or vim.fn.expand("%:p:h") .. "/"

local M = {}

-- Find all Lua files in the current directory
local files = vim.fn.glob(this_dir .. "*.lua", false, true)

for _, file in ipairs(files) do
	local filename = vim.fn.fnamemodify(file, ":t")

	-- Skip the init.lua file to avoid circular requires
	if filename ~= "init.lua" then
		---@diagnostic disable-next-line: undefined-field
		local module_name = filename:gsub("%.lua$", "")
		local ok, mod = pcall(require, "plugins.google." .. module_name)

		if ok and type(mod) == "table" then
			vim.list_extend(M, mod)
		end
	end
end

return M
