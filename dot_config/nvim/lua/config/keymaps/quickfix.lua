--- Keymaps related to the quickfix / location list.

for _, pair in ipairs({ { "c", "quickfix" }, { "l", "location" } }) do
	local char = pair[1]
	local list_type = pair[2]

	-- KEYMAP(N): <leader>qcc
	-- KEYMAP(N): <leader>qlc
	vim.keymap.set(
		"n",
		"<leader>q" .. char .. "c",
		"<cmd>" .. char .. "close<cr>",
		{ desc = "Close the " .. list_type .. " window." }
	)

	-- KEYMAP(N): <leader>qco
	-- KEYMAP(N): <leader>qlo
	vim.keymap.set(
		"n",
		"<leader>q" .. char .. "o",
		"<cmd>" .. char .. "open<cr>",
		{ desc = "Open the " .. list_type .. " window." }
	)

	-- KEYMAP(N): <leader>qcs
	-- KEYMAP(N): <leader>qls
	vim.keymap.set(
		"n",
		"<leader>q" .. char .. "s",
		"<cmd>" .. char .. "do s//~/&<cr><cmd>" .. char .. "fdo update<cr>",
		{ desc = "Re-run last :substitute command on all lines in the " .. list_type .. " list." }
	)
end
