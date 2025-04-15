--- Filetype: qf

local quit_special_buffer = require("util.quit_special_buffer")

-- KEYMAP: q
vim.keymap.set("n", "q", function()
	quit_special_buffer(true)
end, {
	buffer = true,
	desc = "Close the quickfix / location list buffer.",
})
-- KEYMAP: Q
vim.keymap.set("n", "Q", function()
	-- If we are in the location list...
	if vim.fn.get(vim.fn.getloclist(0, { winid = 0 }), "winid", 0) ~= 0 then
		vim.cmd("lclose | Trouble loclist")
		-- Otherwise, we are in the quickfix list.
	else
		vim.cmd("cclose | Trouble quickfix")
	end
end, { buffer = true, desc = "Send the quickfix results to Trouble." })

vim.cmd([[
  function! QuickFixOpenAll()
      if empty(getqflist())
          return
      endif
      let s:prev_val = ""
      for d in getqflist()
          let s:curr_val = bufname(d.bufnr)
          if (s:curr_val != s:prev_val)
              exec "edit " . s:curr_val
          endif
          let s:prev_val = s:curr_val
      endfor
  endfunction
]])

-- KEYMAP: <leader>O
vim.api.nvim_set_keymap("n", "<leader>O", ":call QuickFixOpenAll()<CR>", {
	noremap = true,
	silent = false,
	desc = "Edit ALL files currently loaded in the quickfix list.",
})
