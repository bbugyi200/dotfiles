--- markdown preview plugin for (neo)vim

return {
	-- Install markdown preview, use npx if available.
	--
	-- See https://github.com/iamcco/markdown-preview.nvim/issues/690#issuecomment-2264399766
	"iamcco/markdown-preview.nvim",
	cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
	ft = { "bugged", "codecompanion", "markdown" },
	build = function(plugin)
		if vim.fn.executable("npx") then
			vim.cmd("!cd " .. plugin.dir .. " && cd app && npx --yes yarn install")
		else
			vim.cmd([[Lazy load markdown-preview.nvim]])
			vim.fn["mkdp#util#install"]()
		end
	end,
	init = function()
		if vim.fn.executable("npx") then
			vim.g.mkdp_filetypes = { "bugged", "codecompanion", "markdown" }
		end

		-- KEYMAP: <leader>mdp
		vim.keymap.set("n", "<leader>mdp", "<cmd>MarkdownPreviewToggle<cr>", {
			desc = "MarkdownPreviewToggle",
		})
	end,
}
