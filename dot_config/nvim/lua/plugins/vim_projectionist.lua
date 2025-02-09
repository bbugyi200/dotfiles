--- projectionist.vim: Granular project configuration
--
-- P0: Install https://github.com/tpope/vim-projectionist ?
--   [ ] Use to switch between Dart alternate files!
--   [ ] Add keymaps for ':A', ... (other keymaps?)!
--   [ ] Use projections to define skeleton for new files?!

return {
	-- PLUGIN: http://github.com/tpope/vim-projectionist
	{
		"tpope/vim-projectionist",
		init = function()
			vim.g.projectionist_heuristics = {
				["java/|javatests/"] = {
					["java/com/*.java"] = {
						alternate = "javatests/com/{}Test.java",
						type = "source",
					},
					["javatests/com/*Test.java"] = {
						alternate = "java/com/{}.java",
						type = "test",
					},
				},
			}
		end,
	},
}
