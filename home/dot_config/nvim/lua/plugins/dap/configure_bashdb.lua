--- Configure the debugger for Bash scripts.
local function configure_bashdb()
	local dap = require("dap")
	dap.adapters.bashdb = {
		type = "executable",
		command = vim.fn.stdpath("data") .. "/mason/packages/bash-debug-adapter/bash-debug-adapter",
		name = "bashdb",
	}
	local bashdb_dir = vim.fn.stdpath("data") .. "/mason/packages/bash-debug-adapter/extension/bashdb_dir"
	dap.configurations.sh = {
		{
			type = "bashdb",
			request = "launch",
			name = "Launch file",
			showDebugOutput = true,
			pathBashdb = bashdb_dir .. "/bashdb",
			pathBashdbLib = bashdb_dir,
			trace = true,
			file = "${file}",
			program = "${file}",
			cwd = "${workspaceFolder}",
			pathCat = "cat",
			pathBash = "/bin/bash",
			pathMkfifo = "mkfifo",
			pathPkill = "pkill",
			args = {},
			env = {},
			terminalKind = "integrated",
		},
	}
end

return configure_bashdb
