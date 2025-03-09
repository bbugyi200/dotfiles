--- ChatGPT Neovim Plugin: Effortless Natural Language Generation with OpenAI's ChatGPT API

local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use ChatGPT.
	return {}
else
	return {
		-- PLUGIN: http://github.com/jackMort/ChatGPT.nvim
		{
			"jackMort/ChatGPT.nvim",
			event = "VeryLazy",
			opts = {
				-- P2: Fix password prompt (only necessary once per day)!
				--     (see ~/org/img/chezmoi_pinentry_fix.png!)
				api_key_cmd = "pass show chatgpt_nvim_api_key",
				openai_params = { model = "chatgpt-4o-latest" },
				openai_edit_params = { model = "chatgpt-4o-latest" },
			},
			dependencies = {
				"MunifTanjim/nui.nvim",
				"nvim-lua/plenary.nvim",
				"folke/trouble.nvim", -- optional
				"nvim-telescope/telescope.nvim",
			},
			init = function()
				-- KEYMAP(N+V): <leader>gpe
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpe",
					"<cmd>ChatGPTEditWithInstructions<cr>",
					{ desc = "Edit the current window's contents using ChatGPT." }
				)
				-- KEYMAP(N): <leader>gpg
				vim.keymap.set("n", "<leader>gpg", "<cmd>ChatGPT<cr>", { desc = "Open a ChatGPT prompt." })
			end,
		},
		-- PLUGIN: http://github.com/HPRIOR/telescope-gpt
		{
			"HPRIOR/telescope-gpt",
			dependencies = { "nvim-telescope/telescope.nvim", "jackMort/ChatGPT.nvim" },
			init = function()
				-- KEYMAP(N): <leader>gpt
				vim.keymap.set("n", "<leader>gpt", "<cmd>Telescope gpt<cr>", { desc = "Telescope gpt" })
			end,
		},
	}
end
