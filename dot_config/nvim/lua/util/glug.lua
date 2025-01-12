-- P0: Demote util.glug functions to plugins.google.glugs.

-- M contains this module's public API...
local M = {}
-- ...whereas L is used ONLY locally.
local L = {}

-- Converts a lua value to a vimscript value
local primitives = { number = true, string = true, boolean = true }
L.convert_lua_to_vim = function(value)
	local islist = vim.islist or vim.tbl_islist
	-- Functions refs that match the pattern "function(...)" are returned as is.
	if type(value) == "string" and string.match(value, "^function%(.+%)$") then
		return value
	elseif islist(value) then
		return "[" .. table.concat(vim.tbl_map(L.convert_lua_to_vim, value), ", ") .. "]"
	elseif type(value) == "table" then
		local tbl_str_list = {}
		for key, val in pairs(value) do
			table.insert(tbl_str_list, vim.inspect(key) .. ": " .. L.convert_lua_to_vim(val))
		end
		return "{ " .. table.concat(tbl_str_list, ", ") .. " }"
	elseif type(value) == "boolean" then
		return value and 1 or 0
	elseif primitives[type(value)] then
		return vim.inspect(value)
	end

	error("unsupported type for value: " .. type(value))
end

-- Allow glugin options to be set by `spec.opts`
-- This makes configuring options locally easier
M.glug_opts = function(name, spec)
	if type(spec) == "table" then
		local originalConfig = spec.config
		spec.config = function(plugin, opts)
			if next(opts) ~= nil then
				local cmd = "let s:plugin = maktaba#plugin#Get('" .. name .. "')\n"
				for key, value in pairs(opts) do
					local vim_value = L.convert_lua_to_vim(value)
					cmd = cmd .. "call s:plugin.Flag(" .. vim.inspect(key) .. ", " .. vim_value .. ")\n"
				end
				vim.cmd(cmd)
			end
			if type(originalConfig) == "function" then
				originalConfig(plugin, opts)
			end
		end
	end
	return spec
end

M.glug = function(name, spec)
	return M.glug_opts(
		name,
		vim.tbl_deep_extend("force", {
			name = name,
			dir = "/usr/share/vim/google/" .. name,
			dependencies = { "maktaba" },
		}, spec or {})
	)
end

return M
