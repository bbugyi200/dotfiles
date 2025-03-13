local after_each = require("busted").after_each
local assert = require("busted").assert
local before_each = require("busted").before_each
local describe = require("busted").describe
local it = require("busted").it
local pending = require("busted").pending

--- Scan target path and fetch all top-level file/directory names.
---
---@param path string Path to the target directory.
---@return table<string> List of file/directory names.
local function scandir(path)
	local entries = {}
	-- Determine OS-specific command
	local cmd = package.config:sub(1, 1) == "\\" and ('dir "' .. path .. '" /b') or ('ls -A "' .. path .. '"')
	local handle = io.popen(cmd)
	if handle then
		for entry in handle:lines() do
			table.insert(entries, entry)
		end
		handle:close()
	else
		error("Failed to read directory: " .. path)
	end
	return entries
end

-- P4: Migrate to unit tests, since we don't need an embedded Neovim process?
describe("Smoke test that", function()
	local nvim -- Channel of the embedded Neovim process

	before_each(function()
		-- Start a new Neovim process
		nvim = vim.fn.jobstart({ "nvim", "--embed", "--headless" }, { rpc = true, width = 80, height = 24 })
		local nvim_lua_path = vim.fn.getcwd() .. "/home/dot_config/nvim"
		vim.fn.rpcrequest(nvim, "nvim_command", "set runtimepath+=" .. nvim_lua_path)
	end)

	after_each(function()
		-- Terminate the Neovim process
		vim.fn.jobstop(nvim)
	end)

	local cwd = os.getenv("PWD") or ""
	assert(cwd ~= "", "PWD environment variable is not set")

	local lua_config_files = scandir(cwd .. "/home/dot_config/nvim/lua/config")
	-- strip all .lua extensions from entries
	local config_subpacks = {}
	for _, lua_file in ipairs(lua_config_files) do
		local subpack = lua_file:gsub("%.lua$", "")
		if subpack ~= "lazy_plugins" then
			config_subpacks[#config_subpacks + 1] = subpack
		end
	end

	for _, subpack in ipairs(config_subpacks) do
		it("sources config." .. subpack, function()
			local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
				cmd = "lua",
				args = { string.format("vim.print(pcall(require, 'config.%s'))", subpack) },
				---@diagnostic disable-next-line: redundant-parameter
			}, { output = true })
			local ok, ret = string.match(result, "(%S+)%s*(.*)")
			assert.is_equal(ok, "true", "ERROR IN 'config." .. subpack .. "' MODULE: " .. ret)
			assert.is_equal(ret, "true")
		end)
	end

	-- P4: TEST: sources each module in the plugins.* namespace
	pending("sources each module in the plugins.* namespace")
end)
