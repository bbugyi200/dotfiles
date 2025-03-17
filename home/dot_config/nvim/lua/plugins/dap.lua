--- Debug Adapter Protocol client implementation for Neovim.

local dap_plugin_name = "mfussenegger/nvim-dap"
return {
	-- PLUGIN: http://github.com/mfussenegger/nvim-dap
	{
		dap_plugin_name,
		init = function()
			local dap = require("dap")
			-- KEYMAP(N): <leader>ndb
			vim.keymap.set("n", "<leader>ndb", dap.toggle_breakpoint, {
				desc = "Add a breakpoint.",
			})
			-- KEYMAP(N): <leader>ndc
			vim.keymap.set("n", "<leader>ndc", dap.continue, {
				desc = "Start/continue debugger.",
			})
			-- KEYMAP(N): <leader>ndt
			vim.keymap.set("n", "<leader>ndt", dap.terminate, {
				desc = "Terminate debugger.",
			})
		end,
	},
	-- PLUGIN: http://github.com/rcarriga/nvim-dap-ui
	{
		"rcarriga/nvim-dap-ui",
		opts = {},
		dependencies = { dap_plugin_name, "nvim-neotest/nvim-nio" },
		-- automatically open/close the DAP UI when starting/stopping the debugger
		init = function()
			local dapui = require("dapui")
			local listener = require("dap").listeners

			listener.after.event_initialized["dapui_config"] = dapui.open
			listener.before.event_terminated["dapui_config"] = dapui.close
			listener.before.event_exited["dapui_config"] = dapui.close

			-- KEYMAP(N): <leader>ndu
			vim.keymap.set("n", "<leader>ndu", dapui.toggle, { desc = "Toggle debugger UI." })
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
		init = function()
			require("telescope").load_extension("dap")

			-- KEYMAP(N): <leader>td
			vim.keymap.set("n", "<leader>td", ":Telescope dap ", { desc = "Shortcut for ':Telescope dap'" })
		end,
	},
}
