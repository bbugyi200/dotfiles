--- Configure Lua DAP debugging.
local function configure_lua()
	local dap = require("dap")
	dap.configurations.lua = {
		{
			type = "nlua",
			request = "attach",
			name = "Attach to running Neovim instance",
		},
	}

	dap.adapters.nlua = function(callback, config)
		callback({
			type = "server",
			---@diagnostic disable-next-line: undefined-field
			host = config.host or "127.0.0.1",
			---@diagnostic disable-next-line: undefined-field
			port = config.port or 8086,
		})
	end
end

return configure_lua
