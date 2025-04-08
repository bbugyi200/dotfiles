--- Not UFO in the sky, but an ultra fold in Neovim.

-- P4: Add doc comment!
--- Virutal text handler for UFO.
---
---@generic T
---@param virtText table[T] The virtual text to be displayed.
---@param lnum number The starting line number where the virtual text is displayed.
---@param endLnum number The ending line number where the virtual text is displayed.
---@param width number The width of the window where the virtual text is displayed.
---@param truncate function The function used to truncate the virtual text.
---@return table[T] # The new virtual text to be displayed.
local function fold_virt_text_handler(virtText, lnum, endLnum, width, truncate)
	local newVirtText = {}
	local suffix = (" 󰁂 %d "):format(endLnum - lnum)
	local sufWidth = vim.fn.strdisplaywidth(suffix)
	local targetWidth = width - sufWidth
	local curWidth = 0
	for _, chunk in ipairs(virtText) do
		local chunkText = chunk[1]
		local chunkWidth = vim.fn.strdisplaywidth(chunkText)
		if targetWidth > curWidth + chunkWidth then
			table.insert(newVirtText, chunk)
		else
			chunkText = truncate(chunkText, targetWidth - curWidth)
			local hlGroup = chunk[2]
			table.insert(newVirtText, { chunkText, hlGroup })
			chunkWidth = vim.fn.strdisplaywidth(chunkText)
			-- str width returned from truncate() may less than 2nd argument, need padding
			if curWidth + chunkWidth < targetWidth then
				suffix = suffix .. (" "):rep(targetWidth - curWidth - chunkWidth)
			end
			break
		end
		curWidth = curWidth + chunkWidth
	end
	table.insert(newVirtText, { suffix, "MoreMsg" })
	return newVirtText
end

return {
	-- PLUGIN: http://github.com/kevinhwang91/nvim-ufo
	{
		"kevinhwang91/nvim-ufo",
		dependencies = {
			"kevinhwang91/promise-async",
			-- For repeatable motions using { and }.
			"nvim-treesitter/nvim-treesitter-textobjects",
		},
		opts = {
			fold_virt_text_handler = fold_virt_text_handler,
			provider_selector = function(_, _, _)
				return { "treesitter", "indent" }
			end,
		},
		init = function()
			local ufo = require("ufo")
			local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")

			vim.o.foldcolumn = "0"
			vim.o.foldlevel = 99 -- Using ufo provider need a large value, feel free to decrease the value
			vim.o.foldlevelstart = 99
			vim.o.foldenable = true
			vim.o.fillchars = [[eob: ,fold: ,foldopen:,foldsep: ,foldclose:]]

			-- P4: Add KEYMAP comments for these keymaps.
			vim.keymap.set("n", "zR", ufo.openAllFolds)
			vim.keymap.set("n", "zM", ufo.closeAllFolds)
			vim.keymap.set("n", "zr", ufo.openFoldsExceptKinds)
			vim.keymap.set("n", "zm", ufo.closeFoldsWith) -- closeAllFolds == closeFoldsWith(0)
			vim.keymap.set("n", "zk", ufo.peekFoldedLinesUnderCursor)

			local next_fold, prev_fold =
				repeat_move.make_repeatable_move_pair(ufo.goNextClosedFold, ufo.goPreviousClosedFold)

			-- KEYMAP: [z
			vim.keymap.set("n", "[z", prev_fold, { desc = "Jump to the previous closed fold." })
			-- KEYMAP: ]z
			vim.keymap.set("n", "]z", next_fold, { desc = "Jump to the next closed fold." })
		end,
	},
}
