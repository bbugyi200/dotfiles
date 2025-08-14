local backend = require("plugins.google.codecompanion.goose.backend")
local log = require("plugins.google.codecompanion.goose.log")
local url = require("plugins.google.codecompanion.goose.url")

local M = {}

--- @class CodeCompanionGooseConfig
--- @field auto_start_backend boolean Whether to automatically start go/devai-api-http-proxy
--- @field auto_start_silent boolean Whether to have a silent auto start (don't log status messages)
--- @field temperature number Value controlling the randomness of the output.
--- @field endpoint string DevAI HTTP server prediction service endpoint
--- @field debug boolean Whether to log debug messages
--- @field debug_backend boolean Whether to start backend in debug mode.

--- Default configuration
--- @type CodeCompanionGooseConfig
M.config = {
	auto_start_backend = true,
	auto_start_silent = true,
	temperature = 0.1,
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
--- @param max_decoder_steps number The maximum number of steps to decode.
--- @return table
function M.get_adapter(name, model, max_decoder_steps)
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
			maxDecoderSteps = max_decoder_steps,
		},
		handlers = {
			form_parameters = function(_, params, _)
				return params
			end,
			form_messages = function(_, messages)
				local function convert_role(role)
					if role == "assistant" then
						return "MODEL"
					elseif role == "user" then
						return "USER"
					else
						return role
					end
				end

				local contents = {}
				local system_instruction = nil

				for _, message in ipairs(messages) do
					if message.role == "system" then
						system_instruction = {
							parts = { {
								text = message.content,
							} },
						}
					else
						table.insert(contents, {
							role = convert_role(message.role),
							parts = { {
								text = message.content,
							} },
						})
					end
				end

				local body = {
					model = "models/" .. model,
					client_metadata = {
						feature_name = "codecompanion-goose",
						use_type = "CODE_GENERATION",
					},
					generation_config = {
						temperature = M.config.temperature,
						maxDecoderSteps = max_decoder_steps,
					},
					contents = contents,
				}

				if system_instruction then
					body.system_instruction = system_instruction
				end

				return body
			end,
			chat_output = function(_, data, _)
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

					-- Handle Gemini API response format
					if json.candidates and json.candidates[1] then
						local candidate = json.candidates[1]
						if candidate.finish_reason == "RECITATION" then
							content = "DevAI platform response was blocked for violating policy."
						elseif candidate.content and candidate.content.parts and candidate.content.parts[1] then
							content = candidate.content.parts[1].text or ""
						end
					-- Handle legacy response format
					elseif json.outputs and #json.outputs > 0 then
						if json.output_blocked then
							content = "DevAI platform response was blocked for violating policy."
						else
							for _, output_item in ipairs(json.outputs) do
								if output_item.content then
									content = content .. output_item.content
								end
							end
						end
					-- Handle old array response format
					elseif json[1] then
						for _, output_item in ipairs(json) do
							if output_item.content then
								content = content .. output_item.content
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

					-- Handle Gemini API response format
					if json.candidates and json.candidates[1] then
						local candidate = json.candidates[1]
						if
							candidate.finish_reason ~= "RECITATION"
							and candidate.content
							and candidate.content.parts
							and candidate.content.parts[1]
						then
							content = candidate.content.parts[1].text or ""
						end
					-- Handle legacy response format
					elseif json.outputs and #json.outputs > 0 then
						if not json.output_blocked then
							for _, output_item in ipairs(json.outputs) do
								if output_item.content then
									content = content .. output_item.content
								end
							end
						end
					-- Handle old array response format
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
				default = max_decoder_steps,
				validate = function(n)
					return n > 0, "Must be a positive number"
				end,
				desc = "The maximum number of steps to decode.",
			},
		},
	}
end

return M
