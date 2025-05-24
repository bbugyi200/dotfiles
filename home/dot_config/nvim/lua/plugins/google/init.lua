local bb = require("bb_utils")

if not bb.is_goog_machine() then
	return {}
end

-- Get the directory of the current file
---@diagnostic disable-next-line: undefined-field
local this_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
this_dir = this_dir or vim.fn.expand("%:p:h") .. "/"

local M = {}

-- Helper function to require a module and extend M if successful
local function require_and_extend(module_name)
	local ok, mod = pcall(require, "plugins.google." .. module_name)
	if ok and type(mod) == "table" then
		vim.list_extend(M, mod)
	end
end

-- Find all Lua files in the current directory
local lua_files = vim.fn.glob(this_dir .. "*.lua", false, true)

-- Process direct .lua files
for _, file in ipairs(lua_files) do
	local filename = vim.fn.fnamemodify(file, ":t")

	-- Skip the init.lua file to avoid circular requires
	if filename ~= "init.lua" then
		---@diagnostic disable-next-line: undefined-field
		local module_name = filename:gsub(".lua$", "")
		require_and_extend(module_name)
	end
end

-- Find all directories in the current directory
local dirs = vim.fn.glob(this_dir .. "*/", false, true)

-- Process directories with init.lua
for _, dir in ipairs(dirs) do
	-- Remove trailing slash
	dir = dir:gsub("/$", "")
	local dirname = vim.fn.fnamemodify(dir, ":t")

	-- Check if directory has an init.lua file
	local init_file = dir .. "/init.lua"
	if vim.fn.filereadable(init_file) == 1 then
		require_and_extend(dirname)
	end
end

return M
