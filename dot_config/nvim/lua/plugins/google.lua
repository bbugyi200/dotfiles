-- Run vim commands in terminal.
--
---@param cmd string The vim command to run from the terminal.
local function runInTerm(cmd)
	return function()
		vim.g._term_calling_cmd = 1
		vim.cmd("silent " .. cmd)
		vim.g._term_calling_cmd = 0
	end
end

if require("funcs").on_google_machine() then
	local glug = require("glug").glug
	local glugOpts = require("glug").glugOpts
	local superlazy = require("funcs.superlazy")

	return {
		-- maktaba is required by all google plugins
		glug("maktaba", {
			lazy = true,
			dependencies = {},
			config = function()
				vim.cmd("source /usr/share/vim/google/glug/bootstrap.vim")
			end,
		}),
		glug("relatedfiles", {
			cmd = "RelatedFilesWindow",
			keys = {
				{
					"<leader>sx",
					"<cmd>RelatedFilesWindow<cr>",
					desc = "Show related files",
				},
			},
		}),
		-- Adds G4 support to the vcscommand plugin
		glug("vcscommand-g4", {
			optional = true,
			lazy = true,
		}),
		-- Enable logmsgs ASAP to avoid maktaba's log message queue filling up
		glug("logmsgs", {
			event = "VeryLazy",
		}),
		glug("googler", {
			event = "VeryLazy",
		}),

		-- Add support for google filetypes, these are glugins with `ftdetect` files
		-- This needs to happen on `BufReadPre` for `filetype` to be set properly
		glug("google-filetypes", { event = { "BufReadPre", "BufNewFile" }, dependencies = {} }),
		glug("ft-cel", { event = { "BufReadPre *.cel,*jvp", "BufNewFile *.cel,*jvp" }, dependencies = {} }),
		glug("ft-clif", { event = { "BufReadPre *.clif", "BufNewFile *.clif" }, dependencies = {} }),
		glug("ft-gin", { event = { "BufReadPre *.gin", "BufNewFile *.gin" }, dependencies = {} }),
		glug("ft-gss", { event = { "BufReadPre *.gss", "BufNewFile *.gss" }, dependencies = {} }),
		glug("ft-proto", { event = { "BufReadPre", "BufNewFile" }, dependencies = {} }),
		glug("ft-soy", { event = { "BufReadPre *.soy", "BufNewFile *.soy" }, dependencies = {} }),

		-- Set up syntax, indent, and core settings for various filetypes
		superlazy(glug("ft-cpp", { event = "BufRead,BufNewFile *.[ch],*.cc,*.cpp" })),
		superlazy(glug("ft-go", { event = "BufRead,BufNewFile *.go" })),
		superlazy(glug("ft-java", { event = "BufRead,BufNewFile *.java" })),
		superlazy(glug("ft-javascript", { event = "BufRead,BufNewFile *.js,*.jsx" })),
		superlazy(glug("ft-kotlin", { event = "BufRead,BufNewFile *.kt,*.kts" })),
		superlazy(glug("ft-python", { event = "BufRead,BufNewFile *.py" })),

		-- Configures nvim to respect Google's coding style
		superlazy(glug("googlestyle", { event = { "BufRead", "BufNewFile" } })),

		-- Autogens boilerplate when creating new files
		glug("autogen", {
			event = "BufNewFile",
		}),

		-- Format google code
		glug("codefmt-google", {
			lazy = true,
			opts = function(_, opts)
				local formatters_by_ft = {
					borg = "gclfmt",
					gcl = "gclfmt",
					patchpanel = "gclfmt",
					bzl = "buildifier",
					c = "clang-format",
					cpp = "clang-format",
					javascript = "google-prettier",
					typescript = "google-prettier",
					javascriptreact = "google-prettier",
					typescriptreact = "google-prettier",
					css = "google-prettier",
					scss = "google-prettier",
					html = "google-prettier",
					json = "google-prettier",
					dart = "dartfmt",
					go = "gofmt",
					java = "google-java-format",
					jslayout = "jslfmt",
					markdown = "mdformat",
					ncl = "nclfmt",
					python = "pyformat",
					piccolo = "pyformat",
					soy = "soyfmt",
					textpb = "text-proto-format",
					proto = "protofmt",
					sql = "format_sql",
					googlesql = "format_sql",
					terraform = "terraform",
				}
				local auto_format = {}
				for filetype in pairs(formatters_by_ft) do
					auto_format[filetype] = true
				end
				return vim.tbl_deep_extend("force", opts, {
					formatters_by_ft = formatters_by_ft,
					auto_format = auto_format,
				})
			end,
			-- Setting up autocmds in init allows deferring loading the plugin until
			-- the `BufWritePre` event. One caveat is we must call `codefmt#FormatBuffer()`
			-- manually the first time since the plugin relies on the `BufWritePre` command to call it,
			-- but by the time it's first loaded it has already happened.
			-- TODO: check if that is fixed when the following issue is fixed
			-- https://github.com/folke/lazy.nvim/issues/858
			-- if so, remove the call to `FormatBuffer`
			init = function(plugin)
				local group = vim.api.nvim_create_augroup("autoformat_settings", {})
				local function autocmd(filetype, formatter)
					vim.api.nvim_create_autocmd("FileType", {
						pattern = filetype,
						group = group,
						callback = function(event)
							vim.api.nvim_create_autocmd("BufWritePre", {
								buffer = event.buf,
								group = group,
								once = true,
								callback = function()
									if not vim.g._use_conform_auto_format then
										vim.cmd("call codefmt#FormatBuffer() | AutoFormatBuffer " .. formatter)
									end
								end,
							})
						end,
					})
				end

				-- Build opts from possible parent specs since lazy.nvim doesn't provide it in `init`
				local plugin_opts = require("lazy.core.plugin").values(plugin, "opts", false)
				for filetype, _ in pairs(plugin_opts.auto_format or {}) do
					if plugin_opts.formatters_by_ft[filetype] then
						autocmd(filetype, plugin_opts.formatters_by_ft[filetype])
					end
				end
			end,
		}),

		-- Format code
		glug("codefmt", {
			dependencies = {
				"codefmt-google",
			},
			cmd = { "FormatLines", "FormatCode", "AutoFormatBuffer" },
			event = "BufWritePre",
			opts = {
				clang_format_executable = "/usr/bin/clang-format",
				clang_format_style = "function('codefmtgoogle#GetClangFormatStyle')",
				gofmt_executable = "/usr/lib/google-golang/bin/gofmt",
				dartfmt_executable = { "/usr/lib/google-dartlang/bin/dart", "format" },
				ktfmt_executable = "/google/bin/releases/kotlin-google-eng/ktfmt/ktfmt",
			},
		}),

		-- Run blaze commands
		glug("blaze", {
			opts = {
				execution_mode = "async",
			},
			cmd = {
				"Blaze",
				"BlazeGoToSponge",
				"BlazeViewCommandLog",
				"BlazeLoadErrors",
				"BlazeDebugCurrentFileTest",
				"BlazeDebugCurrentTestMethod",
				"BlazeDebugAddBreakpoint",
				"BlazeDebugClearBreakpoint",
				"BlazeDebugFinish",
			},
			keys = {
				{ "<leader>b", desc = "Blaze" },
				{ "<leader>be", runInTerm("call blaze#LoadErrors()"), desc = "Blaze load errors" },
				{ "<leader>bl", runInTerm("call blaze#ViewCommandLog()"), desc = "Blaze view build log" },
				{ "<leader>bs", runInTerm("BlazeGoToSponge"), desc = "Blaze go to sponge" },
				{ "<leader>bc", runInTerm("Blaze"), desc = "Blaze build on targets" },
				{ "<leader>bb", runInTerm("Blaze build"), desc = "Blaze build" },
				{ "<leader>bt", runInTerm("Blaze test"), desc = "Blaze test" },
				{ "<leader>bf", runInTerm("call blaze#TestCurrentFile()"), desc = "Blaze test current file" },
				{ "<leader>bm", runInTerm("call blaze#TestCurrentMethod()"), desc = "Blaze test current method" },
				{ "<leader>bd", desc = "Blaze debug" },
				{ "<leader>bdf", runInTerm("BlazeDebugCurrentFileTest"), desc = "Blaze debug current file" },
				{ "<leader>bdm", runInTerm("BlazeDebugCurrentTestMethod"), desc = "Blaze debug current method" },
				{ "<leader>bda", runInTerm("BlazeDebugAddBreakpoint"), desc = "Blaze debug add breakpoint" },
				{ "<leader>bdc", runInTerm("BlazeDebugClearBreakpoint"), desc = "Blaze debug clear breakpoint" },
				{ "<leader>bdf", runInTerm("BlazeDebugFinish"), desc = "Blaze debug finish" },
			},
		}),

		-- Blaze imports
		glug("blazedeps", {
			event = "BufWritePost",
			cmd = "BlazeDepsUpdate",
			keys = {
				{ "<leader>bu", runInTerm("BlazeDepsUpdate"), desc = "Blaze update dependencies" },
			},
		}),

		-- Imports
		glug("imp-google", {
			dependencies = {
				glugOpts("vim-imp", {
					"flwyd/vim-imp",
					opts = {
						["Suggest[default]"] = { "buffer", "csearch", "ripgrep", "prompt" },
						["Report[default]"] = "popupnotify",
						["Location[default]"] = "packageroot",
					},
				}),
			},
			cmd = { "ImpSuggest", "ImpFirst" },
			keys = {
				{ "<leader>i", desc = "Import" },
				{ "<leader>ii", "<cmd>ImpSuggest<cr>", desc = "Import list suggestions" },
				{ "<leader>if", "<cmd>ImpFirst<cr>", desc = "Import first suggestion" },
			},
		}),

		-- Adds G4 support to the vcscommand plugin
		glug("vcscommand-g4", {
			optional = true,
			lazy = true,
		}),

		-- A few g4 commands
		glug("g4", {
			event = "FileType piperspec",
			cmd = {
				-- 0 args: edit current file
				-- 1 arg: edit file
				"G4Edit",

				-- 0 args: revert current file
				-- 1 arg: revert file
				"G4Revert",

				-- 0 args: g4 delete current file
				-- 1 arg: g4 delete file
				"G4Delete",

				-- 0 args: move current file (will ask for a new path)
				-- 1 arg: move file (will ask for a new path)
				"G4MoveFile",

				-- 0 args: copy current file  (will ask for a new path)
				-- 1 arg: copy file (will ask for a new path)
				"G4CopyFile",

				-- 0 args: move all files from default to current CL (vim makes a guess)
				-- 1 arg: move all files from default to given CL
				-- 2 args: move all files from first CL to second CL given
				"G4MoveCl",

				-- 0 args: g4 add current file
				-- 1 arg: g4 add file
				"G4Add",

				-- 0 args: g4 diff current file
				-- 1 arg: g4 diff file
				"G4Diff",

				-- 0 args: g4 upload current CL
				-- 1 arg: g4 upload given CL
				"G4Upload",

				-- Show pending changes
				"G4Pending",

				-- Show lint warnings
				"G4Lint",
			},
		}),
		-- Open current file in chrome
		glug("corpweb", {
			dependencies = {
				glug("launchbrowser", { opts = { echo_url = true } }),
				{
					name = "corpweb-preload",
					dir = "/dev/null/corpweb-preload",
					virtual = true,
					config = function()
						-- Disable these mapings before the corpweb glugin
						-- loads, avoiding a warning.
						-- http://google3/devtools/editors/vim/glugins/corpweb/plugin/mappings_gx.vim;l=6-9;rcl=136763367
						--
						-- Using plugin[mappings_gx]=0 won't work since lazy.nvim will load
						-- the `plugin` directory immediately.
						vim.api.nvim_del_keymap("n", "gx")
						vim.api.nvim_del_keymap("n", "g")
						vim.api.nvim_del_keymap("v", "gx")
						vim.api.nvim_del_keymap("v", "g")
					end,
				},
			},
			cmd = {
				-- Launches {query} under codesearch in a web browser
				"CorpWebCs",
				-- Launches the current file under codesearch in a web browser
				"CorpWebCsFile",
				-- Launches the current file doc view (i.e., Cantata, G3Docs, or godoc)
				"CorpWebDocFindFile",
				-- Launches the current CL in Critique
				"CorpWebCritiqueCl",
				-- Launches the current CL in Cider
				"CorpWebCider",
				-- Launches {query} under cs.chromium.org in a web browser
				"CorpWebChromeCs",
			},
		}),

		-- Spellcheck
		superlazy(glug("googlespell", {
			dependencies = {},
			event = {
				"OptionSet spell",
				vim.api.nvim_get_option_value("spell", {}) and "BufRead" or nil,
			},
		})),

		-- Other glugins that may be deprecated but are optional.
		glug("buganizer", {
			optional = true,
			cmd = "BuganizerSearch",
		}),
		superlazy(glug("coverage", {
			optional = true,
			event = "BufRead",
		})),
		glug("critique", {
			optional = true,
			cmd = {
				"CritiqueComments",
				"CritiqueUnresolvedComments",
				"CritiqueNextComment",
				"CritiquePreviousComment",
			},
		}),
		-- Provides :TransformCode command that lets LLMs modify current file/selection.
		--
		-- See http://google3/experimental/users/vvvv/ai.nvim.
		{
			url = "sso://user/vvvv/ai.nvim",
			dependencies = {
				"nvim-lua/plenary.nvim",
			},
			cmd = "TransformCode",
			keys = {
				{ "<leader>tc", "<cmd>TransformCode<cr>", mode = { "n", "v" }, desc = "Transform code" },
			},
		},
		-- Load google paths like //google/* when opening files.
		-- Also works with `gf`, although in mosts cases,
		-- running `vim.lsp.buf.definition()` (by default mapped to `gd`)
		-- over a path will also take you to the file
		--
		-- See http://google3/experimental/users/fentanes/googlepaths.nvim
		{
			url = "sso://user/fentanes/googlepaths.nvim",
			event = { #vim.fn.argv() > 0 and "VeryLazy" or "UIEnter", "BufReadCmd //*", "BufReadCmd google3/*" },
			opts = {},
		},
	}
else
	return {}
end
