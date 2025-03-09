--- Gp.nvim (GPT prompt) Neovim AI plugin
---
--- Gp.nvim (GPT prompt) Neovim AI plugin: ChatGPT sessions & Instructable
--- text/code operations & Speech to text [OpenAI, Ollama, Anthropic, ..].

local is_goog_machine = require("util.is_goog_machine").is_goog_machine

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use external LLM
	-- tools like OpenAI or Anthropic.
	return {}
else
	return {
		-- PLUGIN: http://github.com/Robitx/gp.nvim
		{ "Robitx/gp.nvim", opts = { openai_api_key = "pass show chatgpt_nvim_api_key" } },
	}
end
