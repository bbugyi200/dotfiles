--- Provides :TransformCode command that lets LLMs modify current file/selection.

-- PLUGIN: http://go/cider-agent.nvim
return {
	{
		name = "cider-agent",
		url = "sso://user/idk/cider-agent.nvim",
		init = function()
			local agent = require("cider-agent")
			-- the name of ciderlsp in my configuration is ciderlsp
			agent.setup({ server_name = "ciderlsp" })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>ai
			vim.keymap.set("n", "<leader>ai", "<nop>", { desc = "Ask the AI" })
			-- KEYMAP: <leader>aic
			vim.keymap.set("n", "<leader>aic", function()
				vim.ui.input({ prompt = "Cider Chat: " .. agent.refs() .. "\n" }, agent.chat)
			end, { desc = "Cider [C]hat" })
			-- KEYMAP: <leader>aie
			vim.keymap.set("n", "<leader>aie", function()
				vim.ui.input({ prompt = "Cider Edit: " .. agent.refs() .. "\n" }, agent.simple_coding)
			end, { desc = "Cider [E]dit" })
			-- KEYMAP: <leader>aix
			vim.keymap.set("n", "<leader>aix", function()
				vim.ui.input({ prompt = "Cider Complex Tasks: " .. agent.refs() .. "\n" }, agent.complex_task)
			end, { desc = "Cider Comple[X]" })
		end,
	},
}
