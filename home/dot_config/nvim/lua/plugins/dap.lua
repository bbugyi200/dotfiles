---@diagnostic disable: undefined-field
--- Debug Adapter Protocol client implementation for Neovim.

local dap_plugin_name = "mfussenegger/nvim-dap"

--- Configure hooks that set/delete keymaps that are only active for DAP session.
local function init_keymap_hooks()
	local dap = require("dap")
	local widgets = require("dap.ui.widgets")
	local dapui = require("dapui")

	---@alias DapKeymap { lhs: string, rhs: function, desc: string }
	---@type DapKeymap[]
	local dap_keymaps = {
		{ lhs = "db", rhs = dap.toggle_breakpoint, desc = "Add a breakpoint." },
		{ lhs = "dc", rhs = dap.continue, desc = "Start/continue debugger." },
		{ lhs = "dd", rhs = dap.down, desc = "Go down in current stacktrace." },
		{
			lhs = "de",
			rhs = function()
				vim.ui.input({ prompt = "DAP REPL command: " }, function(text)
					dap.repl.execute(text)
				end)
			end,
			desc = "Execute command in DAP repl.",
		},
		{
			lhs = "di",
			rhs = function()
				dap.step_into({ askForTargets = true })
			end,
			desc = "Step into function/method.",
		},
		{ lhs = "dk", rhs = widgets.hover, desc = "View value of expression under cursor." },
		{ lhs = "do", rhs = dap.step_out, desc = "Step out of function/method." },
		{ lhs = "dr", rhs = dap.run_to_cursor, desc = "Run to cursor." },
		{ lhs = "dR", rhs = dap.repl.toggle, desc = "Toggle DAP repl." },
		{ lhs = "ds", rhs = dap.step_over, desc = "Step over function/method." },
		{ lhs = "du", rhs = dap.up, desc = "Go up in current stacktrace." },
		{ lhs = "dz", rhs = dapui.toggle, desc = "Toggle debugger UI." },
		{ lhs = "q", rhs = dap.terminate, desc = "Terminate debugger." },
	}

	--- Check whether a DAP keymap is defined.
	---
	---@param lhs string The left-hand side of the keymap.
	---@return boolean # True if the keymap is defined, false otherwise.
	local function has_dap_keymap(lhs)
		return vim.fn.maparg(lhs, "n") ~= ""
	end

	---@alias OldKeymap { lhs: string, rhs: string }
	---@type OldKeymap[]
	local old_keymaps = {}

	--- Add keymaps for DAP session.
	local function add_dap_keymaps()
		for _, keymap in ipairs(dap_keymaps) do
			-- Check if the keymap is already defined. If so, save it to restore it later.
			local old_rhs = vim.fn.maparg(keymap.lhs, "n")
			if old_rhs ~= "" then
				table.insert(old_keymaps, { lhs = keymap.lhs, rhs = old_rhs })
			end
			vim.keymap.set("n", keymap.lhs, keymap.rhs, { desc = keymap.desc })
		end
	end

	--- Deletes keymaps for DAP session and restores the previous keymaps.
	local function del_dap_keymaps()
		for _, keymap in ipairs(dap_keymaps) do
			if has_dap_keymap(keymap.lhs) then
				vim.keymap.del("n", keymap.lhs)
				for _, old_keymap in ipairs(old_keymaps) do
					if old_keymap.lhs == keymap.lhs then
						vim.keymap.set("n", old_keymap.lhs, old_keymap.rhs)
					end
				end
			end
		end
	end

	local key = "dap_keymaps"
	dap.listeners.after.event_initialized[key] = add_dap_keymaps
	dap.listeners.before.event_terminated[key] = del_dap_keymaps
	dap.listeners.before.event_exited[key] = del_dap_keymaps
end

return {
	-- PLUGIN: http://github.com/mfussenegger/nvim-dap
	{
		dap_plugin_name,
		init = function()
			-- Configure keymaps that are only active during DAP session.
			init_keymap_hooks()
			-- Configure autocompletion for DAP REPL.
			vim.cmd([[
        au FileType dap-repl lua require('dap.ext.autocompl').attach()
      ]])
		end,
	},
	-- PLUGIN: http://github.com/rcarriga/nvim-dap-ui
	{
		"rcarriga/nvim-dap-ui",
		opts = {},
		dependencies = { dap_plugin_name, "nvim-neotest/nvim-nio" },
		-- automatically open/close the DAP UI when starting/stopping the debugger
		init = function()
			local dap = require("dap")
			local dapui = require("dapui")

			local key = "dapui_config"
			dap.listeners.after.event_initialized[key] = dapui.open
			dap.listeners.before.event_terminated[key] = dapui.close
			dap.listeners.before.event_exited[key] = dapui.close
		end,
	},
	-- PLUGIN: http://github.com/theHamsta/nvim-dap-virtual-text
	{
		"theHamsta/nvim-dap-virtual-text",
		opts = {},
		dependencies = { dap_plugin_name },
	},
	-- PLUGIN: http://github.com/mfussenegger/nvim-dap-python
	{
		"mfussenegger/nvim-dap-python",
		dependencies = { dap_plugin_name },
		config = function()
			local debugpy_pack = require("mason-registry").get_package("debugpy")
			local debugpy_python_bin = debugpy_pack:get_install_path() .. "/venv/bin/python3"
			require("dap-python").setup(debugpy_python_bin)
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-dap.nvim
	{
		"nvim-telescope/telescope-dap.nvim",
		dependencies = { dap_plugin_name },
		init = function()
			require("telescope").load_extension("dap")

			-- KEYMAP(N): <leader>tdc
			vim.keymap.set(
				"n",
				"<leader>tdc",
				"<cmd>Telescope dap commands<cr>",
				{ desc = "Shortcut for ':Telescope dap commands'." }
			)

			-- KEYMAP(N): <leader>tdf
			vim.keymap.set(
				"n",
				"<leader>tdf",
				"<cmd>Telescope dap frames<cr>",
				{ desc = "Shortcut for ':Telescope dap frames'." }
			)
		end,
	},
	-- PLUGIN: http://github.com/LiadOz/nvim-dap-repl-highlights
	{
		"LiadOz/nvim-dap-repl-highlights",
		dependencies = { dap_plugin_name },
		opts = {},
	},
}
