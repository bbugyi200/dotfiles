--- An extensible framework for interacting with tests within NeoVim.

return {
	-- PLUGIN: http://github.com/nvim-neotest/neotest
	{
		"nvim-neotest/neotest",
		dependencies = {
			"nvim-neotest/nvim-nio",
			"nvim-lua/plenary.nvim",
			"nvim-treesitter/nvim-treesitter",
			------- ADAPTERS -------
			"rcasia/neotest-bash", -- Bash
			"MisanthropicBit/neotest-busted", -- Lua
			"nvim-neotest/neotest-python", -- Python
			"mrcjkb/rustaceanvim", -- Rust
		},
		cmd = "Neotest",
		keys = {
			-- KEYMAP: <leader>nta
			{
				"<leader>nta",
				function()
					require("neotest").run.run({ suite = true })
				end,
				desc = "Run all tests using Neotest.",
			},
			-- KEYMAP: <leader>ntd
			{
				"<leader>ntd",
				function()
					---@diagnostic disable-next-line: missing-fields
					require("neotest").run.run({ strategy = "dap" })
				end,
				desc = "Debug nearest test using DAP.",
			},
			-- KEYMAP: <leader>ntf
			{
				"<leader>ntf",
				function()
					require("neotest").run.run(vim.fn.expand("%"))
				end,
				desc = "Run all tests in current file.",
			},
			-- KEYMAP: <leader>ntl
			{
				"<leader>ntl",
				function()
					require("neotest").run.run_last()
				end,
				desc = "Run last set of tests that were run.",
			},
			-- KEYMAP: <leader>nto
			{
				"<leader>nto",
				function()
					vim.cmd([[
            Neotest summary close
            Neotest output-panel
            wincmd j
            wincmd H
          ]])
				end,
				desc = "Run ':Neotest output-panel' command.",
			},
			-- KEYMAP: <leader>ntr
			{
				"<leader>ntr",
				"<cmd>Neotest run<cr>",
				desc = "Run specific test / all tests in file using ':Neotest run'.",
			},
			-- KEYMAP: <leader>nts
			{
				"<leader>nts",
				function()
					vim.cmd([[
          Neotest output-panel close
          Neotest summary toggle
        ]])
				end,
				desc = "Run ':Neotest summary' command.",
			},
		},
		config = function()
			---@diagnostic disable-next-line: missing-fields
			require("neotest").setup({
				adapters = {
					require("neotest-python")({ dap = { justMyCode = false } }),
					require("rustaceanvim.neotest"),
					require("neotest-busted")({ local_luarocks_only = false }),
					require("neotest-bash"),
				},
				consumers = {
					overseer = require("neotest.consumers.overseer"),
				},
			})

			-- AUTOCMD: Configuration that is specific to ':Neotest summary' buffers.
			local bb = require("bb_utils")
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "neotest-summary", "neotest-output-panel" },
				callback = function()
					-- KEYMAP: q
					vim.keymap.set("n", "q", function()
						bb.quit_special_buffer(true)
					end, {
						buffer = true,
						desc = "Close the Neotest buffer.",
					})
				end,
			})
		end,
		init = function()
			-- KEYMAP GROUP: <leader>nt
			vim.keymap.set("n", "<leader>nt", "<nop>", { desc = "Neotest" })
		end,
	},
}
