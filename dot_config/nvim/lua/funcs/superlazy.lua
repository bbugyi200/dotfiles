-- superlazy allows a plugin to be loaded on the `VeryLazy` event and
-- at the same time allow the plugin to bind ot any autocmd events that
-- come before `VeryLazy`, such as `FileType` and `BufRead`.
-- The `VeryLazy` command is fired after the UI is first loaded, using
-- this helps improve app start when neovim is opened with a file.

-- Events to check autocmds for. We target events that could fire before vim fully loads.
local buf_events = { "BufEnter", "BufRead", "BufReadPost", "BufReadPre", "BufWinEnter", "FileType" }
local autocmd_group = vim.api.nvim_create_augroup("superlazy", { clear = false })

-- A unique key to help identify autocmds.
local getAutocmdKey = function(autocmd)
	return table.concat({
		autocmd.event,
		autocmd.group or "",
		autocmd.buffer or "",
		autocmd.pattern or "",
	}, "-")
end

-- Converts a glob pattern used in autocmds to one lua recognizes.
-- Only supports `*` and `[abc]`, no other glob patterns such as `?` and `{a,b,c}`.
local function globPatternToLua(glob_pattern)
	local patterns = {}
	for _, pattern in ipairs(vim.split(glob_pattern, ",")) do
		table.insert(patterns, "^" .. string.gsub(pattern, "*", ".*") .. "$")
	end
	return patterns
end

-- Returns true if file matches pattern.
local function matchPattern(filepath, patterns)
	local filename = string.match(filepath, "/(.*)$") or filepath
	for _, pattern in ipairs(patterns) do
		if string.match(pattern, "/") then
			if string.match(filepath, pattern) then
				return true
			end
		elseif string.match(filename, pattern) then
			return true
		end
	end
	return false
end

local function execAutocmd(autocmd)
	if type(autocmd.callback) == "function" then
		autocmd.callback(autocmd)
	else
		local str_cmd = autocmd.callback or autocmd.command
		if str_cmd ~= "" and not pcall(function()
			vim.cmd(str_cmd)
		end) then
			-- Fallback to using `nvim_exex_autocmds` in case the command fails,
			-- can happen if the command contains buffer specific variables, like <SID>.
			-- Using `nvim_exec_autocmds` can execute all autocmds that match,
			-- not just the given one.
			vim.api.nvim_exec_autocmds(autocmd.event, {
				group = autocmd.group or "",
				pattern = autocmd.pattern,
			})
		end
	end
end

-- If neovim is opened with a file, use VeryLazy, otherwise, use UIEnter.
-- This fixes an issue with the neovim intro screen disappearing.
-- https://github.com/folke/lazy.nvim/issues/1038#issuecomment-1875077735
local uiready_event = #vim.fn.argv() > 0 and { "User", "VeryLazy" } or { "UIEnter", "*" }

local function getPluginName(spec)
	local get_name = require("lazy.core.plugin").Spec.get_name
	local Config = require("lazy.core.config")
	local url
	local name
	if spec[1] then
		local slash = spec[1]:find("/", 1, true)
		if slash then
			local prefix = spec[1]:sub(1, 4)
			if prefix == "http" or prefix == "git@" then
				url = spec.url or spec[1]
			else
				name = spec.name or spec[1]:sub(slash + 1)
				url = spec.url or Config.options.git.url_format:format(spec[1])
			end
		else
			name = spec.name or spec[1]
		end
	end
	return name or spec.dir and get_name(spec.dir) or url and get_name(url)
end

local function loadPlugin(spec)
	local plugin_name = getPluginName(spec)
	local plugin = require("lazy.core.config").plugins[plugin_name]
	if not plugin then
		-- If plugin is disabled, it will not be found.
		return
	end

	-- Take note of which autocmds exist before any plugins are loaded.
	local existing_autocmds = {}
	for _, autocmd in ipairs(vim.api.nvim_get_autocmds({ event = buf_events })) do
		existing_autocmds[getAutocmdKey(autocmd)] = true
	end
	for _, autocmd in ipairs(vim.api.nvim_get_autocmds({ event = buf_events, buffer = vim.api.nvim_list_bufs() })) do
		existing_autocmds[getAutocmdKey(autocmd)] = true
	end

	require("lazy").load({
		plugins = vim.tbl_extend("force", plugin, {
			config = function()
				if plugin.config or plugin.opts then
					require("lazy.core.loader").config(plugin)
				end

				-- Execute any missed autocmd events that fired before the plugin was loaded,
				-- and only for autocmds that were set by this plugin.
				local plugin_autocmds = {}
				for _, autocmd in ipairs(vim.api.nvim_get_autocmds({ event = buf_events })) do
					local autocmd_key = getAutocmdKey(autocmd)
					if not existing_autocmds[autocmd_key] then
						existing_autocmds[autocmd_key] = true
						autocmd.lua_patterns = globPatternToLua(autocmd.pattern)
						table.insert(plugin_autocmds, autocmd)
					end
				end
				for _, autocmd in
					ipairs(vim.api.nvim_get_autocmds({
						event = buf_events,
						buffer = vim.api.nvim_list_bufs(),
					}))
				do
					local autocmd_key = getAutocmdKey(autocmd)
					if not existing_autocmds[autocmd_key] then
						existing_autocmds[autocmd_key] = true
						autocmd.lua_patterns = globPatternToLua(autocmd.pattern)
						table.insert(plugin_autocmds, autocmd)
					end
				end

				local function source_file(path)
					if vim.fn.filereadable(path) == 1 then
						vim.cmd.source(path)
					end
				end

				-- Look through loaded buffers and see if any would activate autocmds.
				for _, bufnr in pairs(vim.api.nvim_list_bufs()) do
					if vim.api.nvim_buf_is_loaded(bufnr) then
						vim.api.nvim_buf_call(bufnr, function()
							for _, autocmd in ipairs(plugin_autocmds) do
								if not autocmd.buflocal or autocmd.buffer == bufnr then
									local match = autocmd.event == "FileType" and vim.bo.filetype
										or vim.api.nvim_buf_get_name(bufnr)
									if matchPattern(match, autocmd.lua_patterns) then
										autocmd.match = match
										autocmd.buf = bufnr
										autocmd.file = vim.api.nvim_buf_get_name(bufnr)
										execAutocmd(autocmd)
									end
								end
							end

							-- Source any ftplugin and syntax files for opened buffers.
							source_file(plugin.dir .. "/ftplugin/" .. vim.bo.filetype .. ".vim")
							source_file(plugin.dir .. "/syntax/" .. vim.bo.filetype .. ".vim")
						end)
					end
				end
			end,
		}),
	})
end

return function(spec)
	local events = {}
	if type(spec.event) == "string" then
		spec.event = { spec.event }
	end
	if type(spec.event) == "table" then
		for _, event_str in ipairs(spec.event) do
			local event, pattern = event_str:match("^(.+)%s+(.*)$")
			table.insert(events, { event or event_str, pattern or "*" })
		end
	end
	if spec.ft then
		table.insert(events, { "FileType", spec.ft })
	end

	local done = false
	for _, event in ipairs(events) do
		vim.api.nvim_create_autocmd(vim.split(event[1], ","), {
			pattern = vim.split(event[2], ","),
			once = true,
			callback = function()
				if done then
					return
				end
				done = true

				-- If this plugin is loaded during startup, defer loading until the UI is ready
				-- to speedup startup time.
				if vim.v.vim_did_enter == 0 then
					vim.api.nvim_create_autocmd(uiready_event[1], {
						pattern = uiready_event[2],
						once = true,
						callback = function()
							loadPlugin(spec)
						end,
						group = autocmd_group,
					})
				else
					-- Otherwise, load the plugin immediately.
					vim.defer_fn(function()
						loadPlugin(spec)
					end, 0)
				end
			end,
			group = autocmd_group,
		})
	end

	-- Make sure plugin loads lazyly and we control when it loads.
	spec.event = nil
	spec.ft = nil
	spec.lazy = true
	return spec
end
