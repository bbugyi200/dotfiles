local cc = require("plugins.codecompanion.common")

return vim.tbl_deep_extend("force", cc.common_plugin_config, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				model = "goose-v3.5-s",
				temperature = 0.1,
				max_decoder_steps = 8192,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					goose = goose.get_adapter(),
				},
				strategies = {
					chat = {
						adapter = "goose",
					},
					inline = {
						adapter = "goose",
					},
					cmd = {
						adapter = "goose",
					},
				},
			}))
		end,
		init = function()
			cc.common_init()

			-- AUTOCMD: Configure 'ge' keymap to comment-paste clipboard and transform code.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
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
				end,
				-- KEYMAP: gE
				vim.keymap.set("n", "gE", function()
					vim.cmd("normal gyge")
				end, { desc = "Implement CodeCompanion edits under cursor using ai.nvim." }),
			})
		end,
	},
})
