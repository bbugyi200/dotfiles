return {
	"nvim-pack/nvim-spectre",
	enabled = false, -- Overriden by lazy_plugins.lua!
	build = "make build-oxi",
	dependencies = { "nvim-lua/plenary.nvim" },
	opts = {
		default = {
			replace = {
				cmd = "oxi",
			},
		},
		use_trouble_qf = true,
	},
	init = function()
		vim.keymap.set("n", "<localleader>ss", '<cmd>lua require("spectre").toggle()<CR>', {
			desc = "Toggle Spectre",
		})
		vim.keymap.set("n", "<localleader>sw", '<cmd>lua require("spectre").open_visual({select_word=true})<CR>', {
			desc = "Search current word",
		})
		vim.keymap.set("v", "<localleader>sw", '<esc><cmd>lua require("spectre").open_visual()<CR>', {
			desc = "Search current word",
		})
		vim.keymap.set("n", "<localleader>sp", '<cmd>lua require("spectre").open_file_search({select_word=true})<CR>', {
			desc = "Search on current file",
		})
	end,
}
