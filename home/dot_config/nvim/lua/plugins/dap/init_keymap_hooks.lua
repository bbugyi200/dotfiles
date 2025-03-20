--- Configure hooks that set/delete keymaps that are only active for DAP session.
local function init_keymap_hooks()
	local dap = require("dap")
	local dap_ui_widgets = require("dap.ui.widgets")
	local dapui = require("dapui")

	---@alias OldKeymap { lhs: string, rhs: string }
	---@type OldKeymap[]
	local old_keymaps = {}

	---@alias DapKeymap { lhs: string, rhs: function, desc: string }
	---@type DapKeymap[]
	local dap_keymaps = {
		{ lhs = "db", rhs = dap.toggle_breakpoint, desc = "Toggle a breakpoint." },
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
		{ lhs = "dk", rhs = dap_ui_widgets.hover, desc = "View value of expression under cursor." },
		{ lhs = "do", rhs = dap.step_out, desc = "Step out of function/method." },
		{ lhs = "dr", rhs = dap.run_to_cursor, desc = "Run to cursor." },
		{ lhs = "ds", rhs = dap.step_over, desc = "Step over function/method." },
		{ lhs = "dt", rhs = dap.repl.toggle, desc = "Toggle DAP repl." },
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

	--- Re-set old keymaps after DAP session ends.
	---
	---@param lhs string The left-hand side of the keymap to restore.
	local function restore_old_keymap(lhs)
		for _, old_keymap in ipairs(old_keymaps) do
			if old_keymap.lhs == lhs then
				vim.keymap.set("n", old_keymap.lhs, old_keymap.rhs)
				break
			end
		end
	end

	--- Deletes keymaps for DAP session and restores the previous keymaps.
	local function del_dap_keymaps()
		for _, keymap in ipairs(dap_keymaps) do
			if has_dap_keymap(keymap.lhs) then
				vim.keymap.del("n", keymap.lhs)
				restore_old_keymap(keymap.lhs)
			end
		end
	end

	local key = "dap_keymaps"
	dap.listeners.after.event_initialized[key] = add_dap_keymaps
	dap.listeners.before.event_terminated[key] = del_dap_keymaps
	dap.listeners.before.event_exited[key] = del_dap_keymaps
end

return init_keymap_hooks
