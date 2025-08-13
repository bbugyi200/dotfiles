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
				debug = true,
				debug_backend = false,
			})

			-- Get default CodeCompanion config to ensure tools are loaded
			local default_config = require("codecompanion.config")
			
			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, default_config, {
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

			-- AUTOCMD: Configure 'ge' keymap to quickly implement clipboard edits.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
						local code_block_pttrn = [[\(\n\n```.*\|^```[a-z]\+\)\n\zs.]]
						vim.fn.search("\\d\\.", "bw")
						vim.cmd('normal W"ayt:')
						vim.cmd('normal W"by$')
						vim.fn.search(code_block_pttrn)
						vim.cmd("normal gy")
						vim.fn.search(code_block_pttrn)
						vim.cmd("wincmd w")
						vim.cmd("edit " .. vim.fn.getreg("a"))
						vim.cmd('normal gg"_dG')
						vim.cmd("normal P")
						vim.cmd("write")
						vim.cmd("wincmd h")
						vim.notify(
							vim.fn.getreg("b"),
							vim.log.levels.INFO,
							{ title = vim.fs.basename(vim.fn.getreg("a")) }
						)
					end, { desc = "Implement clipboard CodeCompanion edits.", buffer = 0 })
				end,
			})
		end,
	},
})
