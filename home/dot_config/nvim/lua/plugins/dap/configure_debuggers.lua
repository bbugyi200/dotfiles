--- Configure the debugger for Bash scripts.
local function configure_bash()
	local dap = require("dap")
	local dap_utils = require("dap.utils")

	-- ADAPTER
	dap.adapters.bashdb = {
		type = "executable",
		command = vim.fn.stdpath("data") .. "/mason/packages/bash-debug-adapter/bash-debug-adapter",
		name = "bashdb",
	}

	-- CONFIGURATIONS
	local bashdb_dir = vim.fn.stdpath("data") .. "/mason/packages/bash-debug-adapter/extension/bashdb_dir"
	local bash_path = vim.fn.executable("/opt/homebrew/bin/bash") == 1 and "/opt/homebrew/bin/bash" or "/bin/bash"
	dap.configurations.sh = {
		{
			type = "bashdb",
			request = "launch",
			name = "file",
			showDebugOutput = true,
			pathBashdb = bashdb_dir .. "/bashdb",
			pathBashdbLib = bashdb_dir,
			trace = true,
			file = "${file}",
			program = "${file}",
			cwd = "${workspaceFolder}",
			pathCat = "cat",
			pathBash = bash_path,
			pathMkfifo = "mkfifo",
			pathPkill = "pkill",
			args = {},
			env = {},
			terminalKind = "integrated",
		},
		{
			type = "bashdb",
			request = "launch",
			name = "file:args",
			showDebugOutput = true,
			pathBashdb = bashdb_dir .. "/bashdb",
			pathBashdbLib = bashdb_dir,
			trace = true,
			file = "${file}",
			program = "${file}",
			cwd = "${workspaceFolder}",
			pathCat = "cat",
			pathBash = bash_path,
			pathMkfifo = "mkfifo",
			pathPkill = "pkill",
			args = function()
				local args_string = vim.fn.input("Arguments: ")
				return dap_utils.splitstr(args_string)
			end,
			env = {},
			terminalKind = "integrated",
		},
	}
end

--- Configure Lua DAP debugging.
local function configure_lua()
	local dap = require("dap")
	-- ADAPTER
	dap.adapters.nlua = function(callback, config)
		callback({
			type = "server",
			---@diagnostic disable-next-line: undefined-field
			host = config.host or "127.0.0.1",
			---@diagnostic disable-next-line: undefined-field
			port = config.port or 8086,
		})
	end

	-- CONFIGURATIONS
	dap.configurations.lua = {
		{
			type = "nlua",
			request = "attach",
			name = "one-step-for-vimkind",
		},
	}
end

--- Configure C/C++/Rust DAP debugging.
local function configure_c_cpp_and_rust()
	local dap = require("dap")

	-- ADAPTER
	dap.adapters.codelldb = {
		type = "executable",
		command = vim.fn.stdpath("data") .. "/mason/packages/codelldb/codelldb",
	}

	-- CONFIGURATIONS
	dap.configurations.rust = {
		{
			name = "Launch file",
			type = "codelldb",
			request = "launch",
			program = function()
				return vim.fn.input("Path to executable: ", vim.fn.getcwd() .. "/", "file")
			end,
			cwd = "${workspaceFolder}",
			stopOnEntry = false,
		},
	}
	dap.configurations.c = dap.configurations.rust
	dap.configurations.cpp = dap.configurations.rust
end

--- Configure DAP debuggers for all supported languages.
local function configure_debuggers()
	configure_bash()
	configure_lua()
	configure_c_cpp_and_rust()
end

return configure_debuggers
