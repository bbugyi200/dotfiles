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

local tool_start_marker = "<ctrl97>tool_code"
local tool_end_marker = "<ctrl98>"

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

--- Generate tool example for model instruction
local function tool_example_for_model()
	local template = [[

Tool invocation is wrapped in markers with tool_code label. Make sure to produce valid json using correct escaping for characters which require that, like double quotes. Example tool invocation:
%s
{
  "name": "view",
  "parameters": {
    "path": "foobar.txt",
    "start_line": 10,
    "end_line": 20
  }
}
%s
]]
	return string.format(template, tool_start_marker, tool_end_marker)
end

--- Extract tool code from text using markers
--- @param text string
--- @return string?, number?, number?
local function extract_tool_code(text)
	local start_marker = tool_start_marker
	local end_marker = tool_end_marker
	local start_pos = string.find(text, start_marker, 1, true) -- plain text search
	if not start_pos then
		return nil, nil, nil
	end
	local end_pos = string.find(text, end_marker, start_pos + #start_marker, true)
	if not end_pos then
		return nil, nil, nil
	end
	local tool_code = string.sub(text, start_pos + #start_marker, end_pos - 1)
	return tool_code, start_pos, end_pos
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
	local adapter = {
		name = "gemini",
		formatted_name = name,
		opts = {
			tools = true,
		},
		features = {
			text = true,
			tools = true,
			vision = false,
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
			maxDecoderSteps = max_decoder_steps,
		},
		handlers = {
			form_parameters = function(_, params, _)
				return params
			end,
			form_messages = function(_, messages, tools)
				log.debug(
					"form_messages called with messages: " .. #messages .. " tools: " .. (tools and "present" or "nil")
				)
				log.debug("All messages: " .. vim.inspect(messages))
				log.debug("Tools parameter type: " .. type(tools))
				if tools then
					log.debug("Tools keys: " .. vim.inspect(vim.tbl_keys(tools)))
				end
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
						local system_text = message.content

						system_instruction = {
							parts = { {
								text = system_text,
							} },
						}
					elseif message.role == "tool" or (message.opts and message.opts.tag == "tool_result") then
						-- Handle tool result messages - just add as user text since we're using text-based format
						table.insert(contents, {
							role = "USER",
							parts = { {
								text = message.content,
							} },
						})
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

				-- Inject tools into system instruction if we have cleaned tools
				if tools and tools._cleaned_tools then
					log.debug("Injecting tools into system prompt")
					local tools_instruction = "\n\nAvailable tools:"
						.. vim.json.encode(tools._cleaned_tools)
						.. tool_example_for_model()

					if body.system_instruction then
						body.system_instruction.parts[1].text = body.system_instruction.parts[1].text
							.. tools_instruction
					else
						body.system_instruction = {
							parts = { {
								text = tools_instruction,
							} },
						}
					end
					log.debug("Updated system instruction: " .. body.system_instruction.parts[1].text)
				else
					-- TEST: Inject a simple test tool when no tools provided by CodeCompanion
					log.debug("*** TEST MODE: Injecting test tool since none provided ***")
					local test_tools = {
						{
							name = "test_tool",
							description = "A test tool to verify tool calling works",
							parameters = {
								{
									name = "message",
									description = "A test message",
									type = "string",
									optional = false,
								},
							},
						},
					}
					local tools_instruction = "\n\nAvailable tools:"
						.. vim.json.encode(test_tools)
						.. tool_example_for_model()

					if body.system_instruction then
						body.system_instruction.parts[1].text = body.system_instruction.parts[1].text
							.. tools_instruction
					else
						body.system_instruction = {
							parts = { {
								text = tools_instruction,
							} },
						}
					end
					log.debug("Updated system instruction with test tool: " .. body.system_instruction.parts[1].text)
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
						-- Check for tool code markers in the response
						local tool_code, start_pos, _ = extract_tool_code(content)
						if tool_code then
							log.debug("Found tool code: " .. tool_code)

							-- Remove tool code from message content
							--- @type string|nil
							local message_content = content:sub(1, start_pos - 1)
							if message_content ~= nil and message_content:match("^%s*$") then
								message_content = nil -- Empty or whitespace only
							end

							-- Try to parse tool code as JSON
							local success, tool_data =
								pcall(vim.json.decode, tool_code:gsub("^%s+", ""):gsub("%s+$", ""))
							if success and tool_data.name and tool_data.parameters then
								output.content = message_content
								output.tool_calls = {
									{
										_index = 1,
										id = "call_1",
										type = "function",
										name = tool_data.name,
										input = tool_data.parameters,
									},
								}
								output.role = "assistant"

								log.debug("Successfully parsed tool call: " .. vim.inspect(output.tool_calls))
								return {
									status = "success",
									output = output,
								}
							else
								log.debug("Failed to parse tool code as JSON: " .. vim.inspect(tool_data))
								-- Fall through to return text content
							end
						end

						-- No tool calls found, return as regular content
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
							-- For inline output, only get text content, ignore function calls
							for _, part in ipairs(candidate.content.parts) do
								if part.text then
									content = content .. (part.text or "")
								end
							end
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

					if content ~= "" then
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
			form_tools = function(self, tools)
				log.debug("*** GOOSE FORM_TOOLS CALLED ***")
				log.debug("self.opts.tools = " .. tostring(self.opts.tools))
				log.debug("tools parameter = " .. (tools and "present" or "nil"))
				if tools then
					log.debug("tools content: " .. vim.inspect(tools))
				end

				if not self.opts.tools then
					log.debug("Tools disabled or not available")
					return nil
				end

				if not tools then
					log.debug("No tools provided to form_tools")
					return nil
				end

				-- Convert CodeCompanion tools to simplified format for text-based calling
				local cleaned_tools = {}
				for _, tool in pairs(tools) do
					for _, schema in pairs(tool) do
						log.debug("Processing tool schema: " .. vim.inspect(schema))

						-- Extract parameters info
						local parameters = {}
						if schema.parameters and schema.parameters.properties then
							for param_name, param_info in pairs(schema.parameters.properties) do
								table.insert(parameters, {
									name = param_name,
									description = param_info.description or "",
									type = param_info.type or "string",
									optional = not (schema.parameters.required and vim.tbl_contains(
										schema.parameters.required,
										param_name
									)),
								})
							end
						end

						table.insert(cleaned_tools, {
							name = schema.name,
							description = schema.description,
							parameters = parameters,
						})
					end
				end

				-- Store cleaned tools for system prompt injection
				self._cleaned_tools = cleaned_tools
				log.debug("*** CLEANED TOOLS FOR SYSTEM PROMPT: " .. vim.inspect(cleaned_tools))

				-- Return nil to indicate we're not using native Gemini function calling
				return nil
			end,

			format_tool_calls = function(_, tools)
				local formatted = {}
				for _, tool in ipairs(tools) do
					local formatted_tool = {
						_index = tool._index,
						id = tool.id,
						type = "function",
						["function"] = {
							name = tool.name,
							arguments = tool.input or tool.arguments,
						},
					}
					table.insert(formatted, formatted_tool)
				end
				return formatted
			end,

			output_response = function(_, tool_call, output)
				log.debug("*** OUTPUT_RESPONSE called ***")
				log.debug("tool_call: " .. vim.inspect(tool_call))
				log.debug("output: " .. vim.inspect(output))

				-- Return tool result in simple text format
				return {
					role = "user",
					content = string.format("```tool_result for %s\n%s\n```", tool_call["function"].name, output),
					opts = {
						visible = false,
						tag = "tool_result",
					},
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

	log.debug("Created adapter with features: " .. vim.inspect(adapter.features))
	log.debug("Adapter tools section: " .. vim.inspect(adapter.tools ~= nil))
	log.debug("Adapter opts: " .. vim.inspect(adapter.opts))

	-- Add debug hook to see when form_tools would be called
	if adapter.tools and adapter.tools.form_tools then
		local original_form_tools = adapter.tools.form_tools
		adapter.tools.form_tools = function(...)
			log.debug("*** FORM_TOOLS HOOK: Called with args ***")
			return original_form_tools(...)
		end
	end

	return adapter
end

return M
