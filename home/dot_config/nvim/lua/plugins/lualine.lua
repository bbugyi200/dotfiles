-- P2: Get line/column number on bottom buffer tab back (with lualine?).
return {
	-- PLUGIN: http://github.com/nvim-lualine/lualine.nvim
	{
		"nvim-lualine/lualine.nvim",
		dependencies = {
			"nvim-tree/nvim-web-devicons",
			"folke/tokyonight.nvim", -- Since we are customizing the tokyonight theme.
		},
		init = function()
			local custom_tokyo = require("lualine.themes.tokyonight")
			custom_tokyo.inactive.c = { fg = "#1f2335", bg = "#828bb8", gui = "bold" }

			-- Custom component for fig commit name with caching
			local fig_commit_cache = {
				value = "",
				last_update = 0,
				update_interval = 60, -- Update every 60 seconds
			}

			local function fig_commit_name()
				local current_time = os.time()

				-- Only update if the cache has expired
				if current_time - fig_commit_cache.last_update > fig_commit_cache.update_interval then
					local handle = io.popen("get_fig_commit_name 2>/dev/null")
					if handle then
						local result = handle:read("*a")
						handle:close()

						-- Trim whitespace
						result = result:gsub("^%s*(.-)%s*$", "%1")

						fig_commit_cache.value = result
						fig_commit_cache.last_update = current_time
					end
				end

				return fig_commit_cache.value
			end

			require("lualine").setup({
				options = {
					icons_enabled = true,
					theme = custom_tokyo,
					component_separators = { left = "", right = "" },
					section_separators = { left = "", right = "" },
					ignore_focus = {},
					always_divide_middle = true,
					always_show_tabline = true,
					globalstatus = false,
					refresh = {
						statusline = 100,
						tabline = 100,
						winbar = 100,
					},
				},
				sections = {
					lualine_a = { "mode" },
					lualine_b = { "branch", fig_commit_name, "diff", "diagnostics" },
					lualine_c = {
						{ "filename", path = 1 },
						{ "aerial", colored = true },
					},
					lualine_x = {
						{ "copilot", show_colors = true },
						"filetype",
					},
					lualine_y = { "progress" },
					lualine_z = { "location" },
				},
				inactive_sections = {
					lualine_a = {},
					lualine_b = {},
					lualine_c = {
						{ "filename", path = 1 },
					},
					lualine_x = {},
					lualine_y = {},
					lualine_z = {},
				},
				tabline = {},
				winbar = {},
				inactive_winbar = {},
				extensions = { "aerial", "fugitive", "lazy", "man", "quickfix", "toggleterm" },
			})
		end,
	},
}
