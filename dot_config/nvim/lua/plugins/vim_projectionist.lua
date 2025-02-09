--- projectionist.vim: Granular project configuration
--
-- P0: Install https://github.com/tpope/vim-projectionist ?
--   [X] Use to switch between Dart alternate files!
--   [ ] Add keymaps for ':A' and ':E*' variants
-- P2: Use projections to define skeleton for new files?!
--     (see [#super_vim_projections] for inspiration!)

return {
	-- PLUGIN: http://github.com/tpope/vim-projectionist
	{
		"tpope/vim-projectionist",
		init = function()
			vim.g.projectionist_heuristics = {
				["java/|javatests/"] = {
					["java/com/*.java"] = {
						alternate = "javatests/com/{}Test.java",
					},
					-- test
					["javatests/com/*Test.java"] = {
						alternate = "java/com/{}.java",
						type = "test",
					},
				},
				["lib/|test/"] = {
					["lib/*.dart"] = {
						alternate = { "lib/{}.acx.html", "lib/{}.scss", "test/{}_test.dart", "testing/lib/{}_po.dart" },
					},
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
					-- test
					["test/*_test.dart"] = {
						alternate = "lib/{}.dart",
						type = "test",
					},
				},
			}
		end,
	},
}
