if require("funcs").on_google_machine() then
	local glug = require("glug").glug
	return {
		-- maktaba is required by all google plugins
		glug("maktaba", {
			lazy = true,
			dependencies = {},
			config = function()
				vim.cmd("source /usr/share/vim/google/glug/bootstrap.vim")
			end,
		}),
		glug("relatedfiles", {
			cmd = "RelatedFilesWindow",
			keys = {
				{
					"<leader>sx",
					"<cmd>RelatedFilesWindow<cr>",
					desc = "Show related files",
				},
			},
		}),
		-- Adds G4 support to the vcscommand plugin
		glug("vcscommand-g4", {
			optional = true,
			lazy = true,
		}),
		-- Provides :TransformCode command that lets LLMs modify current file/selection.
		--
		-- See http://google3/experimental/users/vvvv/ai.nvim.
		{
			url = "sso://user/vvvv/ai.nvim",
			dependencies = {
				"nvim-lua/plenary.nvim",
			},
			cmd = "TransformCode",
			keys = {
				{ "<leader>tc", "<cmd>TransformCode<cr>", mode = { "n", "v" }, desc = "Transform code" },
			},
		},
		-- Load google paths like //google/* when opening files.
		-- Also works with `gf`, although in mosts cases,
		-- running `vim.lsp.buf.definition()` (by default mapped to `gd`)
		-- over a path will also take you to the file
		--
		-- See http://google3/experimental/users/fentanes/googlepaths.nvim.
		{
			url = "sso://user/fentanes/googlepaths.nvim",
			event = { #vim.fn.argv() > 0 and "VeryLazy" or "UIEnter", "BufReadCmd //*", "BufReadCmd google3/*" },
			opts = {},
		},
	}
else
	return {}
end
