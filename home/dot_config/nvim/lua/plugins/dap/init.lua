--- Debug Adapter Protocol client implementation for Neovim.

local init_keymap_hooks = require("plugins.dap.init_keymap_hooks")
local configure_debuggers = require("plugins.dap.configure_debuggers")

local dap_plugin_name = "mfussenegger/nvim-dap"
return {
	-- PLUGIN: http://github.com/mfussenegger/nvim-dap
	{
		dap_plugin_name,
		init = function()
			local dap = require("dap")
			local pbreaks = require("persistent-breakpoints.api")

			-- Configure keymaps that are only active during DAP session.
			init_keymap_hooks()
			-- Configure DAP debuggers for all supported languages.
			configure_debuggers()

			-- KEYMAP(N): <leader>ndbb
			vim.keymap.set("n", "<leader>ndbb", pbreaks.toggle_breakpoint, {
				desc = "Toggle DAP breakpoint for debugging.",
			})
			-- KEYMAP(N): <leader>ndbc
			vim.keymap.set(
				"n",
				"<leader>ndbc",
				pbreaks.set_conditional_breakpoint,
				{ desc = "Set conditional DAP breakpoint for debugging." }
			)
			-- KEYMAP(N): <leader>ndbd
			vim.keymap.set(
				"n",
				"<leader>ndbd",
				pbreaks.clear_all_breakpoints,
				{ desc = "Clear all DAP debugging breakpoints." }
			)
			-- KEYMAP(N): <leader>ndbl
			vim.keymap.set("n", "<leader>ndbl", pbreaks.set_log_point, {
				desc = "Set debugging log point.",
			})
			-- KEYMAP(N): <leader>ndc
			vim.keymap.set("n", "<leader>ndc", dap.continue, {
				desc = "Start DAP debugging session.",
			})
			-- KEYMAP(N): <leader>ndl
			vim.keymap.set("n", "<leader>ndl", dap.run_last, {
				desc = "Start DAP debugging session (use last selected adapter/config).",
			})

			-- Customize DAP sidebar "signs".
			vim.fn.sign_define("DapBreakpoint", { text = "B", texthl = "DiagnosticSignError" })
			vim.fn.sign_define("DapBreakpointCondition", { text = "C", texthl = "DiagnosticSignError" })
			vim.fn.sign_define("DapBreakpointRejected", { text = "R", texthl = "DiagnosticSignError" })
			vim.fn.sign_define("DapLogPoint", { text = "L", texthl = "DiagnosticSignError" })
			vim.fn.sign_define("DapStopped", { text = "→", texthl = "DiagnosticSignError" })

			-- Configure autocompletion for DAP REPL.
			vim.cmd([[
        au FileType dap-repl lua require('dap.ext.autocompl').attach()
      ]])
		end,
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
	-- PLUGIN: http://github.com/jbyuki/one-small-step-for-vimkind
	{
		"jbyuki/one-small-step-for-vimkind",
		dependencies = { dap_plugin_name },
		init = function()
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "lua" },
				callback = function()
					-- KEYMAP(N): <leader>ndo
					vim.keymap.set("n", "<leader>ndo", function()
						require("osv").launch({ port = 8086 })
					end, {
						buffer = true,
						desc = "Launch Lua debugger using one-small-step-for-vimkind.",
					})
				end,
			})
		end,
	},
	-- PLUGIN: http://github.com/mfussenegger/nluarepl
	{
		"mfussenegger/nluarepl",
		dependencies = { dap_plugin_name },
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
	-- PLUGIN: http://github.com/Weissle/persistent-breakpoints.nvim
	{
		"Weissle/persistent-breakpoints.nvim",
		dependencies = { dap_plugin_name },
		opts = { load_breakpoints_event = "BufReadPost" },
	},
}
