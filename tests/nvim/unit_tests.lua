local assert = require("busted").assert
local describe = require("busted").describe
local it = require("busted").it
local pending = require("busted").pending

describe("UNIT TEST:", function()
	-- P4: TEST: flexes bb_utils.delete_file()
	pending("bb_utils.delete_file()")
	-- P4: TEST: flexes bb_utils.copy_to_clipboard()
	pending("bb_utils.copy_to_clipboard()")

	it("selects tmux-osc52 on Linux inside tmux", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))
		local got = provider({ is_mac = false, tmux = true })

		assert.is_not_nil(got)
		assert.is_equal("tmux-osc52", got.name)
		assert.are.same({ "tmux", "load-buffer", "-w", "-" }, got.copy["+"])
		assert.are.same({ "tmux", "load-buffer", "-w", "-" }, got.copy["*"])
		assert.are.same({ "sh", "-c", "tmux save-buffer - 2>/dev/null || true" }, got.paste["+"])
		assert.are.same({ "sh", "-c", "tmux save-buffer - 2>/dev/null || true" }, got.paste["*"])
		assert.is_equal(0, got.cache_enabled)
	end)

	it("returns nil on macOS so Neovim keeps the native clipboard", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))

		assert.is_nil(provider({ is_mac = true, tmux = true }))
		assert.is_nil(provider({ is_mac = true, tmux = false }))
	end)

	it("returns nil on Linux outside tmux so Neovim keeps auto-detection", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))

		assert.is_nil(provider({ is_mac = false, tmux = false }))
	end)

	it("pins vim.g.clipboard from config.clipboard before UIEnter", function()
		local options_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/options.lua"
		local handle = assert(io.open(options_path, "r"))
		local contents = handle:read("*all")
		handle:close()

		local provider_at = contents:find('require%("config%.clipboard"%)', 1)
		local uienter_at = contents:find("UIEnter", 1, true)
		assert.is_truthy(provider_at)
		assert.is_truthy(uienter_at)
		assert.is_true(provider_at < uienter_at)
	end)

	it("configures sase-nvim completion and LSP explicitly", function()
		local sase_nvim_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/plugins/sase_nvim.lua"
		local old_sase_preload = package.preload.sase
		local old_sase_loaded = package.loaded.sase
		local setup_opts

		package.loaded.sase = nil
		package.preload.sase = function()
			return {
				setup = function(opts)
					setup_opts = opts
				end,
			}
		end

		local ok, plugin_spec = pcall(dofile, sase_nvim_path)
		if ok then
			plugin_spec[1].config()
		end

		package.preload.sase = old_sase_preload
		package.loaded.sase = old_sase_loaded

		assert.is_true(ok)
		assert.is_true(setup_opts.complete.keymap)
		assert.is_equal("auto", setup_opts.complete.completion_backend)
		assert.is_true(setup_opts.lsp.enabled)
	end)

	it("shims copilot-cmp is_available to use the method call", function()
		local copilot_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/plugins/copilot.lua"
		local old_bb_loaded = package.loaded.bb_utils
		local old_cmp_loaded = package.loaded["copilot_cmp"]
		local old_source_loaded = package.loaded["copilot_cmp.source"]
		local old_vim = _G.vim
		local setup_opts_seen

		package.loaded.bb_utils = {
			is_goog_machine = function()
				return false
			end,
		}
		package.loaded["copilot_cmp"] = {
			setup = function(opts)
				setup_opts_seen = opts
			end,
		}
		local fake_source = {}
		package.loaded["copilot_cmp.source"] = fake_source
		_G.vim = {
			lsp = {},
			api = {
				nvim_get_current_buf = function()
					return 0
				end,
			},
		}

		local ok, plugin_spec = pcall(dofile, copilot_path)
		local entry
		if ok then
			for _, spec in ipairs(plugin_spec) do
				if spec[1] == "zbirenbaum/copilot-cmp" then
					entry = spec
					break
				end
			end
		end
		assert.is_true(ok)
		assert.is_not_nil(entry)
		assert.is_not_nil(entry.config)
		entry.config(nil, entry.opts)

		assert.is_true(setup_opts_seen == entry.opts)

		local client = { name = "copilot", id = 7 }
		client.is_stopped = function(self)
			assert.is_true(self == client)
			return false
		end
		local fake_clients = { {} }
		_G.vim.lsp.get_clients = function(filter)
			assert.is_equal(0, filter.bufnr)
			assert.is_equal(7, filter.id)
			return fake_clients
		end
		assert.is_true(fake_source.is_available({ client = client }))

		local stopped_client = { name = "copilot", id = 7 }
		stopped_client.is_stopped = function(self)
			assert.is_true(self == stopped_client)
			return true
		end
		assert.is_false(fake_source.is_available({ client = stopped_client }))

		fake_clients = {}
		assert.is_false(fake_source.is_available({ client = client }))
		fake_clients = { {} }
		assert.is_true(fake_source.is_available({ client = client }))

		package.loaded.bb_utils = old_bb_loaded
		package.loaded["copilot_cmp"] = old_cmp_loaded
		package.loaded["copilot_cmp.source"] = old_source_loaded
		_G.vim = old_vim
	end)
end)
