-- P1: Remap 'g?' to '?' and sort by description by default!
-- P3: Create zorg notes for best 'nvim-tree' keymaps!
return {
	-- PLUGIN: http://github.com/nvim-tree/nvim-tree.lua
	{
		"nvim-tree/nvim-tree.lua",
		init = function()
			require("nvim-tree").setup({})
			vim.keymap.set("n", "<localleader>n", function()
				local is_nvim_tree_open = false
				for _, bufinfo in ipairs(vim.fn.getbufinfo()) do
					---@type string
					local buffer_name = bufinfo["name"]
					if buffer_name:match("NvimTree") then
						is_nvim_tree_open = true
						break
					end
				end
				if not is_nvim_tree_open then
					vim.cmd("wincmd o")
				end
				vim.cmd("NvimTreeToggle " .. vim.fn.expand("%:h"))
			end)
		end,
	},
}
