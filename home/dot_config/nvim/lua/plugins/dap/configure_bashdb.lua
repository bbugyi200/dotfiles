--- Configure the debugger for Bash scripts.
local function configure_bashdb()
	local dap = require("dap")
	local dap_utils = require("dap.utils")

	dap.adapters.bashdb = {
		type = "executable",
		command = vim.fn.stdpath("data") .. "/mason/packages/bash-debug-adapter/bash-debug-adapter",
		name = "bashdb",
	}

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

return configure_bashdb
