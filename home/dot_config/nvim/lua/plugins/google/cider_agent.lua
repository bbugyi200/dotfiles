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

			-- KEYMAP: <leader>aI
			vim.keymap.set("n", "<leader>aI", function()
				vim.ui.input({ prompt = "Cider Complex Tasks: " .. agent.refs() .. "\n" }, agent.complex_task)
			end, { desc = "CiderComplex" })
		end,
	},
}
