local is_goog_machine = require("util.is_goog_machine")

if not is_goog_machine() then
	return {}
end

local M = {}
local this_dir = debug.getinfo(1, "S").source:match("@(.*/)")
local plenary_exists, scan = pcall(require, "plenary.scandir")

local files = {}
if plenary_exists then
	-- Use plenary if available for robust scanning
	files = scan.scan_dir(this_dir, { depth = 1, add_dirs = false, search_pattern = ".*%.lua$" })
else
	-- Fallback: use vim.loop
	for name, _ in vim.fs.dir(this_dir) do
		if name:match("%.lua$") and name ~= "init.lua" then
			table.insert(files, this_dir .. name)
		end
	end
end

for _, file in ipairs(files) do
	local mod_name = file:match("lua/(.*)%.lua$"):gsub("/", ".")
	if mod_name ~= "plugins.google.init" then
		local ok, mod = pcall(require, mod_name)
		if ok and type(mod) == "table" then
			vim.list_extend(M, mod)
		end
	end
end

return M
