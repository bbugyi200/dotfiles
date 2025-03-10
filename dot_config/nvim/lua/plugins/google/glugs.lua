local superlazy = require("util.superlazy").superlazy

--- Run vim commands in terminal.
---
---@param cmd string The vim command to run from the terminal.
---@return fun(): nil # A function that runs {cmd} as a system command from the terminal.
local function run_in_term(cmd)
	return function()
		vim.g._term_calling_cmd = 1
		vim.cmd("silent " .. cmd)
		vim.g._term_calling_cmd = 0
	end
end

local glug_opts = (function()
	-- Converts a lua value to a vimscript value
	local primitives = { number = true, string = true, boolean = true }

	--- Converts a Lua value to its equivalent VimScript representation
	---
	---@param value any The Lua value to convert.
	---@return string|integer # The VimScript string representation of the value.
	local function convert_lua_to_vim(value)
		local islist = vim.islist or vim.tbl_islist
		-- Functions refs that match the pattern "function(...)" are returned as is.
		if type(value) == "string" and string.match(value, "^function%(.+%)$") then
			return value
		elseif islist(value) then
			return "[" .. table.concat(vim.tbl_map(convert_lua_to_vim, value), ", ") .. "]"
		elseif type(value) == "table" then
			local tbl_str_list = {}
			for key, val in pairs(value) do
				table.insert(tbl_str_list, vim.inspect(key) .. ": " .. convert_lua_to_vim(val))
			end
			return "{ " .. table.concat(tbl_str_list, ", ") .. " }"
		elseif type(value) == "boolean" then
			return value and 1 or 0
		elseif primitives[type(value)] then
			return vim.inspect(value)
		end

		error("unsupported type for value: " .. type(value))
	end

	--- Process glugin options and configures them for the specified plugin.
	---
	---@generic T : table
	---@param name string The name of the plugin.
	---@param spec T The plugin specification table, which may contain a config field.
	---@return T # The processed plugin specification.
	local function glug_opts(name, spec)
		if type(spec) == "table" then
			local originalConfig = spec.config
			spec.config = function(plugin, opts)
				if next(opts) ~= nil then
					local cmd = "let s:plugin = maktaba#plugin#Get('" .. name .. "')\n"
					for key, value in pairs(opts) do
						local vim_value = convert_lua_to_vim(value)
						cmd = cmd .. "call s:plugin.Flag(" .. vim.inspect(key) .. ", " .. vim_value .. ")\n"
					end
					vim.cmd(cmd)
				end
				if type(originalConfig) == "function" then
					originalConfig(plugin, opts)
				end
			end
		end
		return spec
	end

	return glug_opts
end)()

--- Creates a configuration for a Google VIM plugin (glugin)
---
---@param name string The name of the glugin to configure.
---@param spec? table Optional specification table to override default settings.
---@return table # The processed plugin specification with default values and any overrides.
local function glug(name, spec)
	return glug_opts(
		name,
		vim.tbl_deep_extend("force", {
			name = name,
			dir = "/usr/share/vim/google/" .. name,
			dependencies = { "maktaba" },
		}, spec or {})
	)
end

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
				"<localleader>r",
				"<cmd>RelatedFilesWindow<cr>",
				desc = "Show related files",
			},
		},
	}),
	-- Enable logmsgs ASAP to avoid maktaba's log message queue filling up
	glug("logmsgs", {
		event = "VeryLazy",
	}),
	glug("googler", {
		event = "VeryLazy",
	}),

	-- Provides a command that produces an "outline window".
	glug("outline-window", { cmd = { "GoogleOutlineWindow" } }),

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
			{ "<leader>be", run_in_term("call blaze#LoadErrors()"), desc = "Blaze load errors" },
			{ "<leader>bl", run_in_term("call blaze#ViewCommandLog()"), desc = "Blaze view build log" },
			{ "<leader>bs", run_in_term("BlazeGoToSponge"), desc = "Blaze go to sponge" },
			{ "<leader>bc", run_in_term("Blaze"), desc = "Blaze build on targets" },
			{ "<leader>bb", run_in_term("Blaze build"), desc = "Blaze build" },
			{ "<leader>bt", run_in_term("Blaze test"), desc = "Blaze test" },
			{ "<leader>bf", run_in_term("call blaze#TestCurrentFile()"), desc = "Blaze test current file" },
			{ "<leader>bm", run_in_term("call blaze#TestCurrentMethod()"), desc = "Blaze test current method" },
			{ "<leader>bd", desc = "Blaze debug" },
			{ "<leader>bdf", run_in_term("BlazeDebugCurrentFileTest"), desc = "Blaze debug current file" },
			{ "<leader>bdm", run_in_term("BlazeDebugCurrentTestMethod"), desc = "Blaze debug current method" },
			{ "<leader>bda", run_in_term("BlazeDebugAddBreakpoint"), desc = "Blaze debug add breakpoint" },
			{ "<leader>bdc", run_in_term("BlazeDebugClearBreakpoint"), desc = "Blaze debug clear breakpoint" },
			{ "<leader>bdf", run_in_term("BlazeDebugFinish"), desc = "Blaze debug finish" },
		},
	}),

	-- Blaze imports
	glug("blazedeps", {
		event = "BufWritePost",
		cmd = "BlazeDepsUpdate",
		keys = {
			{ "<leader>bu", run_in_term("BlazeDepsUpdate"), desc = "Blaze update dependencies" },
		},
	}),

	-- Imports
	glug("imp-google", {
		dependencies = {
			glug_opts("vim-imp", {
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
			{ "<leader>i", "<cmd>ImpSuggest<cr>", desc = "Import list suggestions" },
		},
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

	-- Other glugins that MAY be deprecated
	glug("buganizer", {
		cmd = "BuganizerSearch",
	}),
	superlazy(glug("coverage", {
		event = "BufRead",
	})),
	superlazy(glug("coverage-google", {
		event = "BufRead",
		init = function()
			-- KEYMAP(N): <leader>ncc
			vim.keymap.set(
				"n",
				"<leader>ncc",
				"<cmd>CoverageToggle<cr>",
				{ desc = "Toggle go/coverage-google in sign column." }
			)

			-- KEYMAP(N): <leader>ncs
			vim.keymap.set(
				"n",
				"<leader>ncs",
				"<cmd>CoverageStats<cr>",
				{ desc = "Show go/coverage-google file stats." }
			)
		end,
	})),
	glug("critique", {
		cmd = {
			"CritiqueComments",
			"CritiqueUnresolvedComments",
			"CritiqueNextComment",
			"CritiquePreviousComment",
		},
	}),
}
