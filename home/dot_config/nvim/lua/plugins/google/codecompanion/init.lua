local cc = require("plugins.codecompanion.common")
local slash_cmds = require("plugins.google.codecompanion.slash_cmds")

return vim.tbl_deep_extend("force", cc.common_plugin_config, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				temperature = 0.1,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					little_goose = goose.get_adapter("LittleGoose", "goose-v3.5-s", 8192),
					big_goose = goose.get_adapter("BigGoose", "gemini-for-google-2.5-pro", 65536),
				},
				strategies = {
					chat = {
						adapter = "big_goose",
						slash_commands = {
							bugs = slash_cmds.bugs,
							cs = slash_cmds.cs,
							clfiles = slash_cmds.clfiles,
							["local"] = slash_cmds["local"],
						},
					},
					inline = {
						adapter = "big_goose",
					},
					cmd = {
						adapter = "big_goose",
					},
				},
			}))
		end,
		init = function()
			cc.common_init()

			-- KEYMAP: <leader>ccs
			cc.create_adapter_switch_keymap("little_goose", "big_goose")

			-- AUTOCMD: Configure 'ge' keymap to comment-paste clipboard and transform code.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
						if vim.v.count > 0 then
							vim.cmd("normal! y" .. vim.v.count .. "j")
							vim.cmd("normal! " .. vim.v.count + 1 .. "jzz")
						end

						-- Navigate to previous buffer
						vim.cmd("wincmd w")

						-- Jump to bottom of buffer
						vim.cmd("normal! G")

						-- Paste clipboard contents
						vim.cmd("normal! p")

						-- Comment out the pasted content
						vim.cmd("normal gcG")

						-- Run the transform command
						vim.cmd("TransformCode Implement the edits described at the bottom of the file in comments.")
					end, { desc = "Implement clipboard CodeCompanion edits using ai.nvim.", buffer = 0 })

					-- KEYMAP: gE
					vim.keymap.set("n", "gE", function()
						vim.cmd("normal gyge")
					end, { desc = "Implement CodeCompanion edits under cursor using ai.nvim.", buffer = 0 })
				end,
			})
		end,
	},
})
