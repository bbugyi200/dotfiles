--- Build custom shell commands and quickly run snippets of code without leaving NeoVim.

return {
	-- PLUGIN: https://github.com/arjunmahishi/flow.nvim
	{
		"arjunmahishi/flow.nvim",
		opts = {
			custom_cmd_dir = os.getenv("HOME") .. "/.local/share/chezmoi/dot_config/nvim/flow_cmds",
			filetype_cmd_map = { zorg = "bash -c '%s'" },
		},
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			require("telescope").load_extension("flow")

			-- KEYMAP(N): <leader>tf
			vim.keymap.set("n", "<leader>tf", "<cmd>Telescope flow<cr>", { desc = "Telescope flow" })
			-- KEYMAP(X): <leader>f
			vim.keymap.set(
				"x",
				"<leader>f",
				"<cmd>FlowRunSelected<cr>",
				{ desc = "Run visually selected code using Flow." }
			)
			-- KEYMAP(N): <leader>fo
			vim.keymap.set("n", "<leader>fo", "<cmd>FlowLastOutput<cr>", { desc = "View output of last Flow command." })
			-- KEYMAP(N): <leader>ff
			vim.keymap.set("n", "<leader>ff", "<cmd>FlowRunLastCmd<cr>", { desc = "Run last Flow command." })
			-- KEYMAP(N): <leader>fr
			vim.keymap.set("n", "<leader>fr", "<cmd>FlowRunFile<cr>", { desc = "Run code in file using Flow." })
		end,
	},
}
