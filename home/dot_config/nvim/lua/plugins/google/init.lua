local bb = require("bb_utils")

if not bb.is_goog_machine() then
	return {}
end

-- Get the directory of the current file
---@diagnostic disable-next-line: undefined-field
local this_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
this_dir = this_dir or vim.fn.expand("%:p:h") .. "/"

local M = {}

-- Find all items in the current directory
local items = vim.fn.glob(this_dir .. "*", false, true)

for _, item in ipairs(items) do
	local name = vim.fn.fnamemodify(item, ":t")

	-- Skip the init.lua file to avoid circular requires
	if name ~= "init.lua" then
		local module_name
		local should_require = false

		if vim.fn.isdirectory(item) == 1 then
			-- Directory - check if it has an init.lua file
			local init_file = item .. "/init.lua"
			if vim.fn.filereadable(init_file) == 1 then
				module_name = name
				should_require = true
			end
		elseif name:match(".lua$") then
			-- Regular .lua file
			---@diagnostic disable-next-line: undefined-field
			module_name = name:gsub(".lua$", "")
			should_require = true
		end

		if should_require and module_name then
			local ok, mod = pcall(require, "plugins.google." .. module_name)

			if ok and type(mod) == "table" then
				vim.list_extend(M, mod)
			end
		end
	end
end

return M
