--- Gp.nvim (GPT prompt) Neovim AI plugin
---
--- Gp.nvim (GPT prompt) Neovim AI plugin: ChatGPT sessions & Instructable
--- text/code operations & Speech to text [OpenAI, Ollama, Anthropic, ..].

local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use external LLM
	-- tools like OpenAI or Anthropic.
	return {}
else
	return {
		-- PLUGIN: http://github.com/Robitx/gp.nvim
		{
			"Robitx/gp.nvim",
			opts = {
				providers = {
					anthropic = {
						endpoint = "https://api.anthropic.com/v1/messages",
						secret = { "pass", "show", "claude_nvim_api_key" },
					},
					openai = {
						endpoint = "https://api.openai.com/v1/chat/completions",
						secret = { "pass", "show", "chatgpt_nvim_api_key" },
					},
				},
			},
			init = function()
				-- KEYMAP(N): <leader>gpa
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpa",
					":GpAppend<cr>",
					{ desc = "Run :GpAppend (append output after selection)" }
				)

				-- KEYMAP(N): <leader>gpn
				vim.keymap.set("n", "<leader>gpn", "<cmd>GpNextAgent<cr>", { desc = "Run :GpNextAgent" })

				-- KEYMAP(N): <leader>gpp
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpp",
					":GpPrepend<cr>",
					{ desc = "Run :GpPrepend (prepend output before selection)" }
				)

				-- KEYMAP(N+V): <leader>gpr
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpr",
					":GpRewrite<cr>",
					{ desc = "Run :GpRewrite (replace selection w/ output)" }
				)

				-- KEYMAP(N): <leader>gpwa
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpwa",
					":GpWhisperAppend<cr>",
					{ desc = "Run :GpWhisperAppend (append output after selection)" }
				)

				-- KEYMAP(N): <leader>gpwp
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpwp",
					":GpWhisperPrepend<cr>",
					{ desc = "Run :GpWhisperPrepend (prepend output before selection)" }
				)

				-- KEYMAP(N+V): <leader>gpwr
				vim.keymap.set(
					{ "n", "v" },
					"<leader>gpwr",
					":GpWhisperRewrite<cr>",
					{ desc = "Run :GpWhisperRewrite (replace selection w/ output)" }
				)
			end,
		},
	}
end
