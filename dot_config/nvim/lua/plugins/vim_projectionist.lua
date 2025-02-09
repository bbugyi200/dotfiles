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
				["*"] = {
					-- css
					["lib/*.scss"] = {
						alternate = "lib/{}.dart",
						type = "css",
					},
					-- html
					["lib/*.acx.html"] = {
						alternate = "lib/{}.dart",
						type = "html",
					},
					-- po
					["testing/lib/*_po.dart"] = {
						alternate = "lib/{}.dart",
						type = "po",
					},
					-- source
					["java/com/*.java"] = {
						alternate = "javatests/com/{}Test.java",
						type = "source",
					},
					["lib/*.dart"] = {
						alternate = { "lib/{}.acx.html", "lib/{}.scss", "test/{}_test.dart", "testing/lib/{}_po.dart" },
						type = "source",
					},
					-- test
					["javatests/com/*Test.java"] = {
						alternate = "java/com/{}.java",
						type = "test",
					},
					["test/*_test.dart"] = {
						alternate = "lib/{}.dart",
						type = "test",
					},
				},
			}
		end,
	},
}
