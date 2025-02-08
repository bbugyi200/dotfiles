--- projectionist.vim: Granular project configuration

return {
	-- PLUGIN: http://github.com/tpope/vim-projectionist
	{
		"tpope/vim-projectionist",
		init = function()
			vim.g.projectionist_heuristics = {
				["*"] = {
					["src/main/java/*.java"] = {
						alternate = "src/test/java/{}Test.java",
					},
					["src/test/java/*Test.java"] = {
						alternate = "src/main/java/{}.java",
					},
				},
			}
		end,
	},
}
