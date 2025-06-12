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
--- @param name string The name of the adapter.
--- @param model string The Goose model to use.
--- @return table
function M.get_adapter(name, model)
	local openai = require("codecompanion.adapters.openai")
	return {
		name = "goose",
		formatted_name = name,
		opts = {},
		features = {},
		roles = {
			llm = "assistant",
			user = "user",
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
			tokens = function(self, data)
				return openai.handlers.tokens(self, data)
			end,
			form_parameters = function(self, params, messages)
				return openai.handlers.form_parameters(self, params, messages)
			end,
			form_tools = function(self, tools)
				return openai.handlers.form_tools(self, tools)
			end,
			form_messages = function(self, messages)
				return openai.handlers.form_messages(self, messages)
			end,
			chat_output = function(self, data, tools)
				return openai.handlers.chat_output(self, data, tools)
			end,
			tools = {
				format_tool_calls = function(self, tools)
					return openai.handlers.tools.format_tool_calls(self, tools)
				end,
				output_response = function(self, tool_call, output)
					return openai.handlers.tools.output_response(self, tool_call, output)
				end,
			},
			inline_output = function(self, data, context)
				return openai.handlers.inline_output(self, data, context)
			end,
			on_exit = function(self, data)
				return openai.handlers.on_exit(self, data)
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
					"gemini-for-google-2.5-pro",
					"goose-v3.5-s",
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
