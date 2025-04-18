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
					["*.lua"] = {
						alternate = "{dirname}/{dirname|basename}.lua",
					},
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

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>p
			vim.keymap.set("n", "<leader>p", "<nop>", { desc = "Open Related Files (aka projections)" })

			-- KEYMAP: <leader>pp
			vim.keymap.set("n", "<leader>pp", "<cmd>A<cr>", { desc = "Shortcut for the :A projection." })

			local snippet_dir = vim.fn.expand("~/.local/share/chezmoi/home/dot_config/nvim/luasnippets")
			-- KEYMAP: <leader>ps
			vim.keymap.set("n", "<leader>ps", function()
				vim.cmd("e " .. snippet_dir .. "/" .. vim.bo.filetype .. ".lua")
			end, { desc = "Shortcut to open the <FILETYPE>.lua snippet file." })

			-- KEYMAP: <leader>pS
			vim.keymap.set(
				"n",
				"<leader>pS",
				"<cmd>e " .. snippet_dir .. "/all.lua<cr>",
				{ desc = "Shortcut to open the all.lua snippet file." }
			)

			-- AUTOCMD: Add <leader>pt keymap for test pojections.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "dart", "html", "java", "python", "scss" },
				callback = function()
					-- KEYMAP: <leader>pt
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
					-- KEYMAP: <leader>pc
					vim.keymap.set(
						"n",
						"<leader>pc",
						"<cmd>Ecss<cr>",
						{ buffer = true, desc = "Shortcut for the :Ecss projection." }
					)
					-- KEYMAP: <leader>ph
					vim.keymap.set(
						"n",
						"<leader>ph",
						"<cmd>Ehtml<cr>",
						{ buffer = true, desc = "Shortcut for the :Ehtml projection." }
					)
					-- KEYMAP: <leader>po
					vim.keymap.set(
						"n",
						"<leader>po",
						"<cmd>Epo<cr>",
						{ buffer = true, desc = "Shortcut for the :Epo projection." }
					)
				end,
			})

			-- AUTOCMD: Add extra (buffer) keymaps for projections that are specific to Lua files.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "lua" },
				callback = function()
					-- KEYMAP: <leader>pi
					vim.keymap.set("n", "<leader>pi", function()
						vim.cmd("edit " .. vim.fn.expand("%:h") .. "/init.lua")
					end, {
						buffer = true,
						desc = "Shortcut for opening <dir>/init.lua.",
					})
				end,
			})
		end,
	},
}
