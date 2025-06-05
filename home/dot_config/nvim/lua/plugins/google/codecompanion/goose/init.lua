local backend = require("plugins.google.codecompanion.goose.backend")
local log = require("plugins.google.codecompanion.goose.log")
local url = require("plugins.google.codecompanion.goose.url")

local M = {}

--- @class CodeCompanionGooseConfig
--- @field auto_start_backend boolean Whether to automatically start go/devai-api-http-proxy
--- @field auto_start_silent boolean Whether to have a silent auto start (don't log status messages)
--- @field temperature number Value controlling the randomness of the output.
--- @field max_decoder_steps number The maximum number of steps to decode.
--- @field endpoint string DevAI HTTP server prediction service endpoint
--- @field debug boolean Whether to log debug messages
--- @field debug_backend boolean Whether to start backend in debug mode.

--- Default configuration
--- @type CodeCompanionGooseConfig
M.config = {
	auto_start_backend = true,
	auto_start_silent = true,
	temperature = 0.1,
	max_decoder_steps = 8192,
	endpoint = "http://localhost:8649/predict",
	debug = false,
	debug_backend = false,
}

--- Returns backend configuration
--- @return table backend configuration
local function get_backend_config()
	local host, port = url.extract_host_port(M.config.endpoint)
	local backend_config = {
		host = host,
		port = port,
		debug = M.config.debug_backend,
	}
	return backend_config
end

--- Setup function
---
--- @param opts CodeCompanionGooseConfig config
function M.setup(opts)
	M.config = vim.tbl_deep_extend("force", M.config, opts or {})

	-- Setup debug logging
	log.setup(M.config.debug)

	local backend_config = get_backend_config()
	backend.setup(backend_config)

	-- Start the server if auto_start_backend is enabled
	if M.config.auto_start_backend then
		backend.start(M.config.auto_start_silent)
	end

	-- Configure user commands
	vim.api.nvim_create_user_command("CodeCompanionGooseServerStatus", function()
		backend.get_status()
	end, { desc = "Check DevAI server status" })
	vim.api.nvim_create_user_command("CodeCompanionGooseServerStop", function()
		backend.stop()
	end, { desc = "Stop DevAI server" })
	vim.api.nvim_create_user_command("CodeCompanionGooseServerStart", function()
		backend.start()
	end, { desc = "Start DevAI server" })
end

--- Get the CodeCompanion adapter for goose
---
--- @param model string The Goose model to use.
--- @return table
function M.get_adapter(model)
	return {
		name = "goose",
		formatted_name = "Goose",
		opts = {
			tools = true,
		},
		features = {
			tools = true,
		},
		roles = {
			llm = "assistant",
			user = "user",
			tool = "tool",
		},
		url = M.config.endpoint,
		headers = {
			["Content-Type"] = "application/json",
		},
		parameters = {
			model = model,
			temperature = M.config.temperature,
			maxDecoderSteps = M.config.max_decoder_steps,
		},
		handlers = {
			form_parameters = function(_, params, _)
				return params
			end,

			form_tools = function(self, tools)
				if not self.opts.tools or not tools then
					return
				end

				local formatted_tools = {}
				for _, tool in pairs(tools) do
					for _, schema in pairs(tool) do
						table.insert(formatted_tools, schema)
					end
				end

				return { tools = formatted_tools }
			end,

			form_messages = function(_, messages)
				local formatted_messages = {}
				for _, message in ipairs(messages) do
					if message.role == "tool" then
						-- Handle tool responses
						table.insert(formatted_messages, "tool_result: " .. message.content)
					else
						table.insert(
							formatted_messages,
							"<ctrl99>" .. message.role .. "\n" .. message.content .. "<ctrl100>\n"
						)
					end
				end
				return {
					input = table.concat(formatted_messages, "\n") .. "<ctrl99>model\n",
				}
			end,

			chat_output = function(self, data, tools)
				local output = {}

				if data and data ~= "" then
					local ok, json = pcall(vim.json.decode, data.body)
					if not ok then
						log.debug("Failed to decode JSON: " .. vim.inspect(data.body))
						return
					end

					if M.config.debug then
						log.debug("Received response: " .. vim.inspect(json))
					end

					local content = ""

					-- Handle new response format with outputs array
					if json.outputs and #json.outputs > 0 then
						if json.output_blocked then
							content = "DevAI platform response was blocked for violating policy."
						else
							for _, output_item in ipairs(json.outputs) do
								if output_item.content then
									content = content .. output_item.content
								end
							end
						end
					-- Handle legacy response format
					elseif json[1] then
						for _, output_item in ipairs(json) do
							if output_item.content then
								content = content .. output_item.content
							end
						end
					end

					-- Extract tool calls from content if present
					if self.opts.tools and tools and content then
						-- Look for tool call patterns in the content
						-- This is a simplified implementation - you may need to adjust based on goose's actual tool call format
						local tool_call_pattern = "<tool_call>(.-)</tool_call>"
						for tool_call_json in content:gmatch(tool_call_pattern) do
							local tool_ok, tool_data = pcall(vim.json.decode, tool_call_json)
							if tool_ok and tool_data.name then
								table.insert(tools, {
									id = tool_data.id or tostring(math.random(1000000)),
									name = tool_data.name,
									input = tool_data.arguments or tool_data.input or "{}",
								})
								-- Remove tool call from content for cleaner display
								content = content:gsub("<tool_call>.-</tool_call>", "")
							end
						end
					end

					if content and content ~= "" then
						output.content = content
						output.role = "assistant"

						return {
							status = "success",
							output = output,
						}
					end
				end
			end,

			inline_output = function(_, data, _)
				if data and data ~= "" then
					local ok, json = pcall(vim.json.decode, data.body)
					if not ok then
						return nil
					end

					local content = ""

					-- Handle new response format with outputs array
					if json.outputs and #json.outputs > 0 then
						if not json.output_blocked then
							for _, output_item in ipairs(json.outputs) do
								if output_item.content then
									content = content .. output_item.content
								end
							end
						end
					-- Handle legacy response format
					elseif json[1] then
						for _, output_item in ipairs(json) do
							if output_item.content then
								content = content .. output_item.content
							end
						end
					end

					if content and content ~= "" then
						return { status = "success", output = content }
					end
				end

				return nil
			end,
			on_exit = function(_, data)
				if data and data.status >= 400 then
					log.error("Error: %s", data.body)
				end
			end,
		},

		tools = {
			format_tool_calls = function(_, tools)
				local formatted = {}
				for _, tool in ipairs(tools) do
					table.insert(formatted, {
						id = tool.id,
						type = "function",
						["function"] = {
							name = tool.name,
							arguments = tool.input,
						},
					})
				end
				return formatted
			end,

			output_response = function(self, tool_call, output)
				return {
					role = self.roles.tool,
					tool_call_id = tool_call.id,
					content = output,
					opts = { visible = false },
				}
			end,
		},

		schema = {
			model = {
				order = 1,
				mapping = "parameters",
				type = "enum",
				desc = "ID of the model to use from go/goose-models",
				default = model,
				choices = {
					"goose-v3.5-s",
					"goose-v3.5-m",
					"goose-v3-mpp",
				},
			},
			temperature = {
				order = 2,
				mapping = "parameters",
				type = "number",
				default = 0.1,
				validate = function(n)
					return n >= 0 and n <= 1, "Must be between 0 and 1"
				end,
				desc = "Value controlling the randomness of the output. Between 0 and 1, inclusive.",
			},
			max_decoder_steps = {
				order = 3,
				mapping = "parameters",
				type = "number",
				default = M.config.max_decoder_steps,
				validate = function(n)
					return n > 0, "Must be a positive number"
				end,
				desc = "The maximum number of steps to decode.",
			},
		},
	}
end

return M
