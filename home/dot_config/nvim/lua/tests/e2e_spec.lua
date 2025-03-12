local after_each = require("busted").after_each
local assert = require("busted").assert
local before_each = require("busted").before_each
local describe = require("busted").describe
local it = require("busted").it
local pending = require("busted").pending

-- P4: Migrate to unit tests, since we don't need an embedded Neovim process?
describe("End-to-end test that", function()
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

	it("sources each module in the config.* namespace", function()
		local config_modules = {
			"autocmds",
			"commands",
			"keymaps",
			"load_local_configs",
			"options",
			"preload",
		}

		for _, module in ipairs(config_modules) do
			local result = vim.fn.rpcrequest(nvim, "nvim_cmd", {
				cmd = "lua",
				args = { string.format("vim.print(pcall(require, 'config.%s'))", module) },
				---@diagnostic disable-next-line: redundant-parameter
			}, { output = true })
			local ok, ret = string.match(result, "(%S+)%s*(.*)")
			assert.is_equal(ok, "true", "ERROR IN 'config." .. module .. "' MODULE: " .. ret)
			assert.is_equal(ret, "true")
		end
	end)

	-- P4: TEST: sources each module in the plugins.* namespace
	pending("sources each module in the plugins.* namespace")
end)
