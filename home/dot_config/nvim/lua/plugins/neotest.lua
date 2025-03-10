--- An extensible framework for interacting with tests within NeoVim.

return {
	-- PLUGIN: http://github.com/nvim-neotest/neotest
	{
		"nvim-neotest/neotest",
		dependencies = {
			"nvim-neotest/nvim-nio",
			"nvim-lua/plenary.nvim",
			"antoinemadec/FixCursorHold.nvim",
			"nvim-treesitter/nvim-treesitter",
			------- ADAPTERS -------
			"nvim-neotest/neotest-python",
			"mrcjkb/rustaceanvim",
			"MisanthropicBit/neotest-busted",
		},
		config = function()
			---@diagnostic disable-next-line: missing-fields
			require("neotest").setup({
				adapters = {
					require("neotest-python")({ dap = { justMyCode = false } }),
					require("rustaceanvim.neotest"),
					require("neotest-busted"),
				},
			})
		end,
		init = function()
			-- KEYMAP(N): <leader>nta
			vim.keymap.set(
				"n",
				"<leader>nta",
				"<cmd>lua require('neotest').run.run({ suite = true })<cr>",
				{ desc = "Run all tests using Neotest." }
			)

			-- KEYMAP(N): <leader>nto
			vim.keymap.set("n", "<leader>nto", function()
				vim.cmd([[
            Neotest summary close
            Neotest output-panel
            wincmd j
            wincmd H
          ]])
			end, { desc = "Run ':Neotest output-panel' command." })

			-- KEYMAP(N): <leader>ntr
			vim.keymap.set("n", "<leader>ntr", "<cmd>Neotest run<cr>", {
				desc = "Run specific test / all tests in file using the ':Neotest run' command.",
			})

			-- KEYMAP(N): <leader>nts
			vim.keymap.set("n", "<leader>nts", function()
				vim.cmd([[
          Neotest output-panel close
          Neotest summary toggle
        ]])
			end, {
				desc = "Run ':Neotest summary' command.",
			})

			-- AUTOCMD: Configuration that is specific to ':Neotest summary' buffers.
			local quit_special_buffer = require("util.quit_special_buffer")
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "neotest-summary", "neotest-output-panel" },
				callback = function()
					-- KEYMAP(N): q
					vim.keymap.set("n", "q", function()
						quit_special_buffer(true)
					end, {
						buffer = true,
						desc = "Close the ':Neotest summary' buffer.",
					})
				end,
			})
		end,
	},
}
