local after_each = require("busted").after_each
local assert = require("busted").assert
local before_each = require("busted").before_each
local describe = require("busted").describe
local it = require("busted").it

--- Helper to fetch the full */nvim directory path.
---
---@return string # Absolute path to the Neovim configuration directory.
local function get_nvim_path()
	local cwd = os.getenv("PWD") or ""
	assert(cwd ~= "", "PWD environment variable is not set")
	return cwd .. "/home/dot_config/nvim"
end

--- Scan target path and fetch all top-level file/directory names.
---
---@param parent_pack_base string Name of the parent directory.
---@return table<string> # List of all basenames in the parent directory.
local function get_all_subpacks(parent_pack_base)
	local parent_pack = get_nvim_path() .. "/lua/" .. parent_pack_base

	local all_file_names = {}
	-- Determine OS-specific command
	local cmd = package.config:sub(1, 1) == "\\" and ('dir "' .. parent_pack .. '" /b')
		or ('ls -A "' .. parent_pack .. '"')
	local handle = io.popen(cmd)
	if handle then
		for entry in handle:lines() do
			table.insert(all_file_names, entry)
		end
		handle:close()
	else
		error("Failed to read directory: " .. parent_pack)
	end
	local subpacks = {}
	for _, lua_file in ipairs(all_file_names) do
		local subpack = lua_file:gsub("%.lua$", "")
		subpacks[#subpacks + 1] = subpack
	end
	return subpacks
end

-- P4: Migrate to unit tests, since we don't need an embedded Neovim process?
describe("SMOKE TEST:", function()
	local nvim -- Channel of the embedded Neovim process

	before_each(function()
		-- Start a new Neovim process
		nvim = vim.fn.jobstart({ "nvim", "--embed", "--headless" }, { rpc = true, width = 80, height = 24 })
		local nvim_path = get_nvim_path()
		vim.fn.rpcrequest(nvim, "nvim_command", "set runtimepath+=" .. nvim_path)
	end)

	after_each(function()
		-- Terminate the Neovim process
		vim.fn.jobstop(nvim)
	end)

	local config_subpacks = get_all_subpacks("config")
	for _, subpack in ipairs(config_subpacks) do
		if subpack ~= "lazy_plugins" then
			it("require('config." .. subpack .. "')", function()
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
	end

	local plugin_subpacks = get_all_subpacks("plugins")
	for _, subpack in ipairs(plugin_subpacks) do
		it("require('plugins." .. subpack .. "')", function()
			local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
				cmd = "lua",
				args = { string.format("vim.print(pcall(require, 'plugins.%s'))", subpack) },
				---@diagnostic disable-next-line: redundant-parameter
			}, { output = true })
			local ok, ret = string.match(result, "(%S+)%s*(.*)")
			assert.is_equal(ok, "true", "ERROR IN 'plugins." .. subpack .. "' MODULE: " .. ret)
		end)
	end
end)
