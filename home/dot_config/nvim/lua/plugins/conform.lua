local bb = require("bb_utils")

local g_slow_format_filetypes = {}
local g_conform_opts = {}
local g_codefmt = {}
local g_codefmt_opts = {}

-- P4: Add doc comment with @param and @return annotations!
local function formatting_configured_for_ft(ft)
	return g_conform_opts.formatters_by_ft and g_conform_opts.formatters_by_ft[ft]
end

-- P4: Add doc comment with @param and @return annotations!
local function formatting_enabled_in_plugin_for_ft(ft, plugin_opts)
	return plugin_opts.auto_format
		and (plugin_opts.auto_format[ft] or plugin_opts.formatters_by_ft and not plugin_opts.formatters_by_ft[ft])
end

-- P4: Add doc comment with @param and @return annotations!
local function formatting_enabled_for_ft(ft)
	return formatting_configured_for_ft(ft)
		and formatting_enabled_in_plugin_for_ft(ft, g_conform_opts)
		and (not g_codefmt or formatting_enabled_in_plugin_for_ft(ft, g_codefmt_opts))
end

-- P4: Add doc comment with @param and @return annotations!
local function get_conform_opts()
	if bb.is_goog_machine() then
		return function(_, opts)
			local formatters_by_ft = {
				bash = { "shfmt" },
				borg = { "gclfmt" },
				bzl = { "buildifier" },
				c = { "clang_format" },
				cpp = { "clang_format" },
				css = { "prettier" },
				dart = { "dartfmt", "tidy_dart" },
				gcl = { "gclfmt" },
				go = { "gofmt" },
				googlesql = { "format_sql" },
				html = { "prettier" },
				java = { "google-java-format" },
				javascript = { "prettier" },
				javascriptreact = { "prettier", lsp_format = "never" },
				jslayout = { "jslfmt" },
				json = { "prettier" },
				markdown = { "mdformat" },
				ncl = { "nclfmt" },
				patchpanel = { "gclfmt" },
				piccolo = { "pyformat" },
				proto = { "protofmt" },
				python = { "pyformat" },
				scss = { "prettier" },
				soy = { "soyfmt" },
				sql = { "format_sql" },
				terraform = { "terraform" },
				textpb = { "txtpbfmt" },
				typescript = { "prettier" },
				typescriptreact = { "prettier" },
			}
			local auto_format = {}
			for filetype in pairs(formatters_by_ft) do
				if auto_format[filetype] == nil then
					auto_format[filetype] = true
				end
			end
			return vim.tbl_deep_extend("force", opts, {
				default_format_opts = {
					lsp_format = "prefer",
				},
				notify_on_error = true,
				notify_no_formatters = true,
				formatters_by_ft = formatters_by_ft,
				auto_format = auto_format,
				-- Format synchronously at first. But if the LSP or formatter takes too long,
				-- add the filetype to `g_slow_format_filetypes` and use async formatting.
				format_on_save = function(bufnr)
					if vim.g.disable_autoformat or vim.b[bufnr].disable_autoformat then
						return
					end
					if g_slow_format_filetypes[vim.bo[bufnr].filetype] then
						return
					end
					if not formatting_enabled_for_ft(vim.bo[bufnr].filetype) then
						return
					end
					local function on_format(err)
						if err and err:match("timeout$") then
							g_slow_format_filetypes[vim.bo[bufnr].filetype] = true
						end
					end

					return { timeout_ms = 500 }, on_format
				end,
				format_after_save = function(bufnr)
					if vim.g.disable_autoformat or vim.b[bufnr].disable_autoformat then
						return
					end
					if not g_slow_format_filetypes[vim.bo[bufnr].filetype] then
						return
					end
					if not formatting_enabled_for_ft(vim.bo[bufnr].filetype) then
						return
					end
					return {}
				end,
				formatters = {
					gclfmt = {
						command = "/google/data/ro/projects/borg/gclfmt",
						args = {},
						stdin = true,
						range_args = function(ctx)
							return { "--incremental", "--lines", ctx.range.start[1], ":", ctx.range["end"][1], "-" }
						end,
					},
					mdformat = {
						command = "/google/bin/releases/corpeng-engdoc/tools/mdformat",
						args = {},
						range_args = function(ctx)
							return { "-", "--lines", ctx.range.start[1], ":", ctx.range["end"][1] }
						end,
						stdin = true,
					},
					nclfmt = {
						command = "/google/src/head/depot/google3/configlang/ncl/release/nclfmt.k8",
						args = { "-" },
						stdin = true,
					},
					jslfmt = {
						command = "/google/data/ro/projects/gws/tools/direct/jslayout_builder",
						args = { "--mode=format", "-" },
						stdin = true,
					},
					txtpbfmt = {
						command = "/google/bin/releases/text-proto-format/public/fmt",
						args = {},
						stdin = true,
					},
					protofmt = {
						command = "/google/bin/releases/client-proto-wg/protofmt/protofmt",
						args = {},
						stdin = true,
					},
					format_sql = {
						command = "/google/data/ro/teams/googlesql-formatter/fmt",
						args = {},
						stdin = true,
					},
					pyformat = {
						command = "pyformat",
						args = { "--assume_filename", "$FILENAME" },
						stdin = true,
						range_args = function(ctx)
							return { "--lines", ctx.range.start[1] .. "-" .. ctx.range["end"][1] }
						end,
					},
					soyfmt = {
						command = "/google/data/rw/teams/frameworks-web-tools/soy/format/live/bin_deploy.jar",
						args = { "--assume_filename", "$FILENAME" },
						stdin = true,
						range_args = function(ctx)
							return { "--lines", ctx.range.start[1] .. "-" .. ctx.range["end"][1] }
						end,
					},
					tidy_dart = {
						command = "/google/data/ro/teams/tidy_dart/tidy_dart",
						args = { "--stdinFilename", "$FILENAME" },
						stdin = true,
					},
					dartfmt = {
						command = "/usr/lib/google-dartlang/bin/dart",
						args = { "format" },
						stdin = true,
					},
					terraform = {
						command = "/google/data/ro/teams/terraform/bin/terraform",
						args = {},
						stdin = true,
					},
					prettier = {
						command = "/google/data/ro/teams/prettier/prettier",
						args = { "--stdin-filepath", "$FILENAME" },
						stdin = true,
					},
				},
			})
		end
	else
		return {
			format_on_save = {
				-- These options will be passed to conform.format()
				timeout_ms = 500,
				lsp_format = "fallback",
			},
			formatters_by_ft = {
				bash = { "shfmt" },
				lua = { "stylua" },
				-- Conform will run multiple formatters sequentially
				python = { "isort", "black", lsp_format = "fallback" },
				-- You can customize some of the format options for the filetype (:help conform.format)
				rust = { "rustfmt", lsp_format = "fallback" },
			},
		}
	end
end

return {
	-- PLUGIN: http://github.com/stevearc/conform.nvim
	{
		"stevearc/conform.nvim",
		event = "BufWritePre",
		cmd = { "ConformInfo", "Format", "FormatDisable", "FormatEnable" },
		opts = get_conform_opts(),
		config = function(_, opts)
			vim.api.nvim_create_user_command("Format", function(args)
				local range = nil
				if args.count ~= -1 then
					local end_line = vim.api.nvim_buf_get_lines(0, args.line2 - 1, args.line2, true)[1]
					range = {
						start = { args.line1, 0 },
						["end"] = { args.line2, end_line:len() },
					}
				end
				require("conform").format({
					async = true,
					-- CiderLSP doesn't support range formatting.
					lsp_format = range and "never" or "prefer",
					range = range,
				})
			end, { range = true })

			vim.api.nvim_create_user_command("FormatDisable", function(args)
				if args.bang then
					-- FormatDisable! will disable formatting just for this buffer
					vim.b.disable_autoformat = true
				else
					vim.g.disable_autoformat = true
				end
			end, {
				desc = "Disable autoformat on save",
				bang = true,
			})

			vim.api.nvim_create_user_command("FormatEnable", function()
				vim.b.disable_autoformat = false
				vim.g.disable_autoformat = false
				if not formatting_configured_for_ft(vim.bo[0].filetype) then
					vim.notify("Formatting enabled but no formatters configured for this filetype", vim.log.levels.WARN)
				elseif not formatting_enabled_for_ft(vim.bo[0].filetype) then
					vim.notify(
						"Formatting enabled but `opts.auto_format` not set for this filetype",
						vim.log.levels.WARN
					)
				end
			end, {
				desc = "Re-enable autoformat on save",
			})

			g_conform_opts = opts
			g_codefmt = require("lazy.core.config").plugins["codefmt-google"]
			g_codefmt_opts = require("lazy.core.plugin").values(g_codefmt or {}, "opts", false)

			if g_codefmt and not g_codefmt_opts.auto_format or not g_conform_opts.auto_format then
				-- If codefmt is enabled but its `opts.auto_format` disabled,
				-- or if conform.nvim's `opts.formatters_by_ft` is disabled,
				-- disable auto formatting for conform.nvim
				vim.g.disable_autoformat = true
			elseif opts.auto_format and (opts.format_on_save or opts.format_after_save) then
				-- If auto formatting is enabled for conform.nvim, disable it on codefmt.
				vim.g._use_conform_auto_format = true
			end

			require("conform").setup(opts)
		end,
	},
}
