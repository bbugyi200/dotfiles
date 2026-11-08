--- Stateless clipboard provider for remote Neovim inside tmux.
--
-- Do not use Neovim's built-in `tmux` or `osc52` providers: both paste by
-- querying the terminal (OSC 52 read), which makes kitty prompt and `p` stall.
-- Copy goes through `tmux load-buffer -w` (OSC 52 write); paste reads the local
-- tmux buffer only.

---@class ClipboardEnv
---@field is_mac boolean
---@field tmux boolean|string|nil

---@class ClipboardProvider
---@field name string
---@field copy table<string, string[]>
---@field paste table<string, string[]>
---@field cache_enabled integer

local TMUX_COPY = { "tmux", "load-buffer", "-w", "-" }
-- An empty buffer list would otherwise surface as a provider error on paste.
local TMUX_PASTE = { "sh", "-c", "tmux save-buffer - 2>/dev/null || true" }

--- Return a `vim.g.clipboard` provider for this environment, or nil so Neovim
--- keeps its default auto-detection (macOS pbcopy, or local X11).
---@param opts ClipboardEnv
---@return ClipboardProvider|nil
local function provider(opts)
	opts = opts or {}
	if opts.is_mac then
		return nil
	end
	if opts.tmux then
		return {
			name = "tmux-osc52",
			copy = {
				["+"] = TMUX_COPY,
				["*"] = TMUX_COPY,
			},
			paste = {
				["+"] = TMUX_PASTE,
				["*"] = TMUX_PASTE,
			},
			cache_enabled = 0,
		}
	end
	return nil
end

return provider
