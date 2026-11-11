--- Enable code completion using Copilot.

local bb = require("bb_utils")

if bb.is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use Copilot.
	return {}
else
	local copilot_plugin_name = "zbirenbaum/copilot.lua"
	return {
		-- PLUGIN: http://github.com/zbirenbaum/copilot.lua
		{
			copilot_plugin_name,
			cmd = "Copilot",
			event = "InsertEnter",
			opts = {
				suggestion = { enabled = true },
				panel = { enabled = true },
				filetypes = {
					dart = true,
					lua = true,
					java = true,
					markdown = true,
					python = true,
					rust = true,
					shell = true,
					yaml = true,
				},
			},
		},
		-- PLUGIN: http://github.com/zbirenbaum/copilot-cmp
		{
			"zbirenbaum/copilot-cmp",
			opts = {},
			dependencies = { copilot_plugin_name },
			config = function(_, opts)
				-- Shim for the deprecated client.is_stopped dot-call in
				-- copilot-cmp (lua/copilot_cmp/source.lua:23): use the method
				-- call and fix the copilot name check. Drop this override if
				-- upstream fixes line 23. Patching the module table covers
				-- every instance via setmetatable __index.
				local source = require("copilot_cmp.source")
				function source.is_available(self)
					if self.client:is_stopped() or self.client.name ~= "copilot" then
						return false
					end
					local clients = vim.lsp.get_clients({ bufnr = vim.api.nvim_get_current_buf(), id = self.client.id })
					return next(clients) ~= nil
				end
				require("copilot_cmp").setup(opts)
			end,
		},
		-- PLUGIN: http://github.com/AndreM222/copilot-lualine
		{ "AndreM222/copilot-lualine", dependencies = { copilot_plugin_name } },
	}
end
