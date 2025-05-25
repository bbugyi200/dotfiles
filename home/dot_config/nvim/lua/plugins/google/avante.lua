return {
	{
		"yetone/avante.nvim",
		build = "make",
		commit = "f9aa754",
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"stevearc/dressing.nvim",
			"nvim-lua/plenary.nvim",
			"MunifTanjim/nui.nvim",
			-- Add vintharas/avante-goose.nvim as a dependecy to avante.nvim
			-- That'll ensure that you'll load avante-goose when you load avante.
			{
				"vintharas/avante-goose.nvim",
				url = "sso://user/vintharas/avante-goose.nvim",
				opts = {
					-- Add your options here
					-- These are the defaults
					auto_start_backend = true, -- Whether to automatically start go/devai-api-http-proxy. If false you can use :AvanteGooseServerStart to start the server
					auto_start_silent = true, -- Whether to have a silent auto start (don't log status messages)
					model = "goose-v3.5-s", -- Select model from go/goose-models.
					temperature = 0.1, -- Model temperature
					max_decoder_tokens = 512, -- Max decoder tokens
					endpoint = "http://localhost:8080/predict", -- Endpoint to start/listen to go/devai-api-http-proxy
					debug = false, -- Enables debug mode (outputs lots of logs for troubleshooting issues)
					debug_backend = false, -- Whether to start the backend in debug mode. This logs backend output information under stdpath('cache')/devai-http-wrapper.log
				},
			},
		},
		opts = {
			provider = "goose", -- Select goose as provider
			vendors = {}, -- Makes sure there's a vendors table
		},
		config = function(_, opts)
			-- Load provider from the plugin
			opts.vendors["goose"] = require("avante-goose").getProvider()
			require("avante").setup(opts)
		end,
		init = function()
			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         Keymaps                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>av
			vim.keymap.set({ "n", "v" }, "<leader>av", "<nop>", { desc = "avante.nvim" })

			-- KEYMAP: <leader>ava
			vim.keymap.set({ "n", "v" }, "<leader>ava", "<cmd>AvanteAsk<cr>", { desc = "AvanteAsk" })

			-- KEYMAP: <leader>ave
			vim.keymap.set({ "n", "v" }, "<leader>ave", "<cmd>AvanteEdit<cr>", { desc = "AvanteEdit" })

			-- KEYMAP: <leader>avh
			vim.keymap.set({ "n", "v" }, "<leader>avh", "<cmd>AvanteHistory<cr>", { desc = "AvanteHistory" })

			-- KEYMAP: <leader>avm
			vim.keymap.set({ "n", "v" }, "<leader>avm", "<cmd>AvanteModels<cr>", { desc = "AvanteModels" })

			-- AUTOCMD: Configure keymaps for AvanteInput buffer.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "AvanteInput", "AvantePromptInput" },
				callback = function()
					-- KEYMAP: <cr>
					vim.keymap.set("n", "<cr>", function()
						-- Yank the query to my clipboard.
						vim.cmd("normal! ggyG")
						-- Simulate keypress to tirgger keymap that submits query!
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
					end, { buffer = true, desc = "Submit Avante query." })

					-- KEYMAP: <c-q>
					vim.keymap.set("i", "<c-q>", function()
						-- Exit insert mode
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, true, true), "n", false)
						-- Yank the query to my clipboard.
						vim.cmd("normal! ggyG")
						-- Simulate keypress to tirgger keymap that submits query!
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
					end, { buffer = true, desc = "Submit Avante query from insert mode." })
				end,
			})
		end,
	},
}
