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
					["*.py"] = { alternate = "{dirname}/__init__.py" },
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
				["src/&tests/"] = {
					["tests/*.py"] = { alternate = "src/{}.py", type = "test" },
				},
			}

			-- KEYMAP(N): <leader>pa
			vim.keymap.set("n", "<leader>pa", "<cmd>A<cr>", { desc = "Shortcut for the :A projection." })

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
