local cc = require("plugins.codecompanion.common")

return vim.tbl_deep_extend("force", cc.common_plugin_config, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				temperature = 0.1,
				max_decoder_steps = 8192,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					little_goose = goose.get_adapter("goose-v3.5-s"),
					big_goose = goose.get_adapter("goose-v3.5-m-rl-153236463"),
				},
				strategies = {
					chat = {
						adapter = "little_goose",
					},
					inline = {
						adapter = "little_goose",
					},
					cmd = {
						adapter = "little_goose",
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

			-- KEYMAP: <leader>ccs
			vim.keymap.set("n", "<leader>ccs", function()
				local config = require("codecompanion.config")
				local current = config.strategies.chat.adapter
				local new = current == "little_goose" and "big_goose" or "little_goose"

				for _, strategy in pairs(config.strategies) do
					strategy.adapter = new
				end

				vim.notify("Switched CodeCompanion adapter to " .. new, vim.log.levels.INFO)
			end, { desc = "Switch AI Adapter" })
		end,
	},
})
