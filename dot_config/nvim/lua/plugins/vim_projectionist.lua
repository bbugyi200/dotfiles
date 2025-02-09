--- projectionist.vim: Granular project configuration

return {
	-- PLUGIN: http://github.com/tpope/vim-projectionist
	{
		"tpope/vim-projectionist",
		init = function()
			vim.g.projectionist_heuristics = {
				["*"] = {
					["java/com/*.java"] = {
						alternate = "javatests/com/{}Test.java",
					},
					["javatests/com/*Test.java"] = {
						alternate = "java/com/{}.java",
					},
				},
			}
		end,
	},
}
