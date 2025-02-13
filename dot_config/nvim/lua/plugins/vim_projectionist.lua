--- projectionist.vim: Granular project configuration
--
-- P2: Use projections to define skeleton for new files?!
--     (see [#super_vim_projections] for inspiration!)

return {
	-- PLUGIN: http://github.com/tpope/vim-projectionist
	{
		"tpope/vim-projectionist",
		init = function()
			vim.g.projectionist_heuristics = {
				["*"] = {
					["*.lua"] = { alternate = "{dirname}/init.lua" },
				},
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
				["src/|tests/"] = {
					["src/*.py"] = { alternate = { "src/{dirname}/__init__.py", "tests/test_{basename}.py" } },
					["src/**/_*.py"] = { alternate = { "src/{dirname}/__init__.py", "tests/test_{basename}.py" } },
					["tests/test_*.py"] = { alternate = "tests/conftest.py", type = "test" },
				},
			}

			-- KEYMAP(C): a (":a " -> ":A ")
			vim.cmd([[
        cabbrev a <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "A" : "a"<CR>
      ]])
			-- KEYMAP(N): <leader>pp
			vim.keymap.set("n", "<leader>pp", "<cmd>A<cr>", { desc = "Shortcut for the :A projection." })

			-- AUTOCMD: Add <leader>pt keymap for test pojections.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "dart", "html", "java", "python", "scss" },
				callback = function()
					-- KEYMAP(N): <leader>pt
					vim.keymap.set(
						"n",
						"<leader>pt",
						"<cmd>Etest<cr>",
						{ buffer = true, desc = "Shortcut for the :Etest projection." }
					)
				end,
			})

			-- AUTOCMD: Add extra (buffer) keymaps for projections that are specific to Dart/HTML/SCSS files.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "dart", "html", "scss" },
				callback = function()
					-- KEYMAP(N): <leader>pc
					vim.keymap.set(
						"n",
						"<leader>pc",
						"<cmd>Ecss<cr>",
						{ buffer = true, desc = "Shortcut for the :Ecss projection." }
					)
					-- KEYMAP(N): <leader>ph
					vim.keymap.set(
						"n",
						"<leader>ph",
						"<cmd>Ehtml<cr>",
						{ buffer = true, desc = "Shortcut for the :Ehtml projection." }
					)
					-- KEYMAP(N): <leader>po
					vim.keymap.set(
						"n",
						"<leader>po",
						"<cmd>Epo<cr>",
						{ buffer = true, desc = "Shortcut for the :Epo projection." }
					)
				end,
			})
		end,
	},
}
