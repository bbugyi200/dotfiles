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
	local holder_nvim -- Channel of an embedded Neovim process that owns a swap file
	local temp_dirs = {}

	before_each(function()
		-- Start a new Neovim process
		nvim = vim.fn.jobstart({ "nvim", "--embed", "--headless" }, { rpc = true, width = 80, height = 24 })
		local nvim_path = get_nvim_path()
		vim.fn.rpcrequest(nvim, "nvim_command", "set runtimepath^=" .. nvim_path)
		vim.fn.rpcrequest(nvim, "nvim_command", "set runtimepath+=" .. nvim_path .. "/after")
	end)

	after_each(function()
		-- Terminate the Neovim process
		if holder_nvim then
			vim.fn.jobstop(holder_nvim)
			holder_nvim = nil
		end
		vim.fn.jobstop(nvim)

		for _, temp_dir in ipairs(temp_dirs) do
			vim.fn.delete(temp_dir, "rf")
		end
		temp_dirs = {}
	end)

	local function make_temp_dir()
		local temp_dir = vim.fn.tempname()
		vim.fn.mkdir(temp_dir, "p")
		table.insert(temp_dirs, temp_dir)
		return temp_dir
	end

	local function wait_for_swapfile(temp_dir)
		local swapfile
		local found_swapfile = vim.wait(2000, function()
			local matches = vim.fn.glob(temp_dir .. "/*.swp", false, true)
			swapfile = matches[1]
			return swapfile ~= nil
		end, 50)

		assert.is_true(found_swapfile, "Timed out waiting for swap file in " .. temp_dir)
		return swapfile
	end

	it("require('config.*')", function()
		local config_subpacks = get_all_subpacks("config")
		for _, subpack in ipairs(config_subpacks) do
			if subpack ~= "lazy_plugins" then
				local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
					cmd = "lua",
					args = { string.format("vim.print(pcall(require, 'config.%s'))", subpack) },
					---@diagnostic disable-next-line: redundant-parameter
				}, { output = true })
				local ok, ret = string.match(result, "(%S+)%s*(.*)")
				assert.is_equal(ok, "true", "ERROR IN 'config." .. subpack .. "' MODULE: " .. ret)
			end
		end
	end)

	it("require('plugins.*')", function()
		local plugin_subpacks = get_all_subpacks("plugins")
		for _, subpack in ipairs(plugin_subpacks) do
			local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
				cmd = "lua",
				args = { string.format("vim.print(pcall(require, 'plugins.%s'))", subpack) },
				---@diagnostic disable-next-line: redundant-parameter
			}, { output = true })
			local ok, ret = string.match(result, "(%S+)%s*(.*)")
			assert.is_equal(ok, "true", "ERROR IN 'plugins." .. subpack .. "' MODULE: " .. ret)
		end
	end)

	it("require('bb_utils.*')", function()
		local util_subpacks = get_all_subpacks("bb_utils")
		for _, subpack in ipairs(util_subpacks) do
			local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
				cmd = "lua",
				args = { string.format("vim.print(pcall(require, 'bb_utils.%s'))", subpack) },
				---@diagnostic disable-next-line: redundant-parameter
			}, { output = true })
			local ok, ret = string.match(result, "(%S+)%s*(.*)")
			assert.is_equal(ok, "true", "ERROR IN 'bb_utils." .. subpack .. "' MODULE: " .. ret)
		end
	end)

	it("enables spell checking for markdown buffers", function()
		vim.fn.rpcrequest(nvim, "nvim_command", "filetype plugin on")
		vim.fn.rpcrequest(nvim, "nvim_command", "enew")
		vim.fn.rpcrequest(nvim, "nvim_command", "set filetype=markdown")

		local filetype = vim.fn.rpcrequest(nvim, "nvim_get_option_value", "filetype", { buf = 0 })
		local spell = vim.fn.rpcrequest(nvim, "nvim_get_option_value", "spell", { win = 0 })

		assert.is_equal("markdown", filetype)
		assert.is_true(spell)
	end)

	it("toasts and edits anyway when a swap file exists", function()
		local temp_dir = make_temp_dir()
		local target_file = temp_dir .. "/swap-target.txt"
		vim.fn.writefile({ "hello" }, target_file)

		holder_nvim = vim.fn.jobstart({
			"nvim",
			"--clean",
			"--headless",
			"--cmd",
			"set directory=" .. temp_dir .. "//",
			target_file,
			"+sleep 10000m",
		}, { width = 80, height = 24 })
		assert.is_true(holder_nvim > 0)
		local swapfile = wait_for_swapfile(temp_dir)

		vim.fn.rpcrequest(nvim, "nvim_command", "set directory=" .. temp_dir .. "//")
		vim.fn.rpcrequest(
			nvim,
			"nvim_exec_lua",
			[[
			_G.swap_notifications = {}
			vim.notify = function(message, level, opts)
				table.insert(_G.swap_notifications, {
					message = message,
					level = level,
					swapchoice = vim.v.swapchoice,
					title = opts and opts.title,
				})
			end
			require("config.autocmds")
		]],
			{}
		)
		vim.fn.rpcrequest(nvim, "nvim_command", "edit " .. vim.fn.fnameescape(target_file))

		local opened_file = vim.fn.rpcrequest(nvim, "nvim_buf_get_name", 0)
		local notifications = vim.fn.rpcrequest(nvim, "nvim_exec_lua", "return _G.swap_notifications", {})
		local swap_notification

		for _, notification in ipairs(notifications) do
			if notification.message:find("Opening", 1, true) then
				swap_notification = notification
				break
			end
		end

		assert.is_equal(target_file, opened_file)
		assert.is_not_nil(swap_notification)
		assert.is_equal(vim.log.levels.WARN, swap_notification.level)
		assert.is_equal("e", swap_notification.swapchoice)
		assert.matches(target_file, swap_notification.message, 1, true)
		assert.matches(swapfile, swap_notification.message, 1, true)
	end)
end)
