--- Integrate fidget.nvim with CodeCompanion.
---
--- INSPIRED BY: http://github.com/olimorris/codecompanion.nvim/discussions/813.

local progress = require("fidget.progress")

local M = {}

--- Initializes the integration between CodeCompanion and fidget.nvim
--- Sets up autocommands to track request lifecycle and display progress notifications
function M:init()
	local group = vim.api.nvim_create_augroup("CodeCompanionFidgetHooks", {})

	vim.api.nvim_create_autocmd({ "User" }, {
		pattern = "CodeCompanionRequestStarted",
		group = group,
		callback = function(request)
			local handle = M:create_progress_handle(request)
			M:store_progress_handle(request.data.id, handle)
		end,
	})

	vim.api.nvim_create_autocmd({ "User" }, {
		pattern = "CodeCompanionRequestFinished",
		group = group,
		callback = function(request)
			local handle = M:pop_progress_handle(request.data.id)
			if handle then
				M:report_exit_status(handle, request)
				handle:finish()
			end
		end,
	})
end

M.handles = {}

--- Stores a fidget progress handle associated with a CodeCompanion request ID.
--- @param id string: Unique identifier for the CodeCompanion request.
--- @param handle table: The fidget progress handle instance to store.
function M:store_progress_handle(id, handle)
	M.handles[id] = handle
end

--- Removes and returns the fidget progress handle associated with the given request ID.
--- @param id string: Unique identifier for the CodeCompanion request.
--- @return table|nil: The removed fidget progress handle, or nil if not found.
function M:pop_progress_handle(id)
	local handle = M.handles[id]
	M.handles[id] = nil
	return handle
end

--- Creates a new fidget progress handle for a CodeCompanion request.
--- @param request table: The request data from CodeCompanion.
--- @return table: A new fidget progress handle tracking this request.
function M:create_progress_handle(request)
	return progress.handle.create({
		title = " Requesting assistance (" .. request.data.strategy .. ")",
		message = "In progress...",
		lsp_client = {
			name = M:llm_role_title(request.data.adapter),
		},
	})
end

--- Formats the LLM adapter and model name into a role title for fidget LSP display.
--- @param adapter table: Adapter object with formatted_name and optional model string.
--- @return string: The composed display name for the LSP client.
function M:llm_role_title(adapter)
	local parts = {}
	table.insert(parts, adapter.formatted_name)
	if adapter.model and adapter.model ~= "" then
		table.insert(parts, "(" .. adapter.model .. ")")
	end
	return table.concat(parts, " ")
end

--- Updates the progress handle with a completion message depending on request status.
--- @param handle table: The fidget progress handle to update.
--- @param request table: The CodeCompanion request object containing a status code.
function M:report_exit_status(handle, request)
	if request.data.status == "success" then
		handle.message = "Completed"
	elseif request.data.status == "error" then
		handle.message = " Error"
	else
		handle.message = "󰜺 Cancelled"
	end
end

return M
