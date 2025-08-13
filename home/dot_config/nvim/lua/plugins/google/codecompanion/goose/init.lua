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
--- @field enable_tools boolean Whether to enable tool support
--- @field tool_start_marker string Start marker for tool invocations
--- @field tool_end_marker string End marker for tool invocations

--- Default configuration
--- @type CodeCompanionGooseConfig
M.config = {
	auto_start_backend = true,
	auto_start_silent = true,
	temperature = 0.1,
	endpoint = "http://localhost:8080/v1/generateContent",
	debug = false,
	debug_backend = false,
	enable_tools = true,
	tool_start_marker = "<ctrl97>tool_code",
	tool_end_marker = "<ctrl98>",
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

--- Tool definitions for CodeCompanion integration
local tools = {
	{
		name = "view",
		description = "The view tool allows you to examine the contents of a file or list the contents of a directory. It can read the entire file or a specific range of lines. If the file content is already in the context, do not use this tool.\nIMPORTANT NOTE: If the file content exceeds a certain size, the returned content will be truncated, and `is_truncated` will be set to true. If `is_truncated` is true, use the `start_line` parameter and `end_line` parameter to specify the range to view.",
		parameters = {
			{
				name = "path",
				description = "The path to the file in the current project scope",
				type = "string",
			},
			{
				name = "start_line",
				description = "The start line of the view range, 1-indexed",
				type = "integer",
				optional = true,
			},
			{
				name = "end_line",
				description = "The end line of the view range, 1-indexed, and -1 for the end line means read to the end of the file",
				type = "integer",
				optional = true,
			},
		},
		returns = {
			{
				name = "content",
				description = "Contents of the file",
				type = "string",
			},
			{
				name = "error",
				description = "Error message if the file was not read successfully",
				type = "string",
				optional = true,
			},
		},
	},
}

--- Creates tool example for the model
local function tool_example_for_model()
	local template = [[
Tool invocation is wrapped in backticks with tool_code label. Make sure to produce valid json using correct escaping for characters which require that, like double quotes. Example tool invocation:
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
	return string.format(template, M.config.tool_start_marker, M.config.tool_end_marker)
end

--- Execute the view tool
local function execute_view_tool(params)
	local path = params.path
	local start_line = params.start_line
	local end_line = params.end_line

	if not path then
		return {
			is_error = true,
			content = "Path parameter is required",
		}
	end

	-- Convert relative path to absolute if needed
	if not vim.startswith(path, "/") then
		path = vim.fn.getcwd() .. "/" .. path
	end

	-- Check if file exists
	if vim.fn.filereadable(path) ~= 1 then
		return {
			is_error = true,
			content = "File not found: " .. path,
		}
	end

	-- Read file content
	local lines = vim.fn.readfile(path)
	local total_line_count = #lines

	-- Apply line range if specified
	local content_lines = lines
	if start_line or end_line then
		local start_idx = start_line and start_line or 1
		local end_idx = end_line and (end_line == -1 and total_line_count or end_line) or total_line_count

		start_idx = math.max(1, start_idx)
		end_idx = math.min(total_line_count, end_idx)

		if start_idx <= end_idx then
			content_lines = vim.list_slice(lines, start_idx, end_idx)
		else
			content_lines = {}
		end
	end

	local content = table.concat(content_lines, "\n")
	local is_truncated = false

	-- Check if content should be truncated (simple check for very large content)
	if #content > 100000 then
		content = string.sub(content, 1, 100000) .. "\n... (content truncated)"
		is_truncated = true
	end

	return {
		is_error = false,
		content = vim.json.encode({
			content = content,
			is_truncated = is_truncated,
			total_line_count = total_line_count,
		}),
	}
end

--- Executes a tool call
local function execute_tool(tool_name, parameters)
	if tool_name == "view" then
		return execute_view_tool(parameters)
	end

	return {
		is_error = true,
		content = "Unknown tool: " .. tool_name,
	}
end

--- Extract tool code from text
local function extract_tool_code(text)
	local start_marker = M.config.tool_start_marker
	local end_marker = M.config.tool_end_marker

	local start_pos = string.find(text, start_marker, 1, true)
	if not start_pos then
		return nil, nil, nil
	end

	local end_pos = string.find(text, end_marker, start_pos + #start_marker, true)
	if not end_pos then
		return nil, nil, nil
	end

	local tool_code = string.sub(text, start_pos + #start_marker, end_pos - 1)
	return tool_code:match("^%s*(.-)%s*$"), start_pos, end_pos -- trim whitespace
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
						local system_text = message.content

						-- Add tool information to system prompt if tools are enabled
						if M.config.enable_tools then
							system_text = system_text
								.. "\nAvailable tools:"
								.. vim.json.encode(tools)
								.. "\n"
								.. tool_example_for_model()
						end

						system_instruction = {
							parts = { {
								text = system_text,
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
						-- Check for tool calls if tools are enabled
						if M.config.enable_tools then
							local tool_code, start_pos, end_pos = extract_tool_code(content)
							if tool_code then
								-- Extract the non-tool part of the response
								local before_tool = string.sub(content, 1, start_pos - 1)
								local after_tool = string.sub(content, end_pos + #M.config.tool_end_marker)
								local response_text = before_tool .. after_tool

								-- First, return the text response if there's any meaningful content
								if response_text and response_text:match("%S") then
									output.content = response_text
									output.role = "assistant"
									-- Add a marker to indicate tool execution will follow
									output.content = output.content .. "\n\n*Executing tool call...*"
								end

								-- Parse and execute the tool
								local success, tool_data = pcall(vim.json.decode, tool_code)
								if success and tool_data.name and tool_data.parameters then
									local tool_result = execute_tool(tool_data.name, tool_data.parameters)

									-- Format tool result for display
									local tool_output = ""
									if tool_result.is_error then
										tool_output = "**Tool Error**: " .. tool_result.content
									else
										-- For view tool, format the output nicely
										if tool_data.name == "view" then
											local result_data = vim.json.decode(tool_result.content)
											tool_output = string.format(
												"**File: %s**\n```\n%s\n```",
												tool_data.parameters.path,
												result_data.content
											)
											if result_data.is_truncated then
												tool_output = tool_output
													.. "\n*Note: Content was truncated due to size*"
											end
										else
											tool_output = "**Tool Result**: " .. tool_result.content
										end
									end

									if output.content then
										output.content =
											output.content:gsub("%*Executing tool call%.%.%.%*", tool_output)
									else
										output.content = tool_output
									end
								else
									local error_msg = "**Tool Execution Error**: Failed to parse tool call: "
										.. tool_code
									if output.content then
										output.content = output.content:gsub("%*Executing tool call%.%.%.%*", error_msg)
									else
										output.content = error_msg
									end
								end

								output.role = "assistant"
								return {
									status = "success",
									output = output,
								}
							end
						end

						-- No tool call found, return content as-is
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
						-- For inline output, we typically don't want tool execution
						-- but we should strip out any tool markers
						if M.config.enable_tools then
							local tool_code, start_pos, end_pos = extract_tool_code(content)
							if tool_code then
								-- Remove tool code from inline output
								local before_tool = string.sub(content, 1, start_pos - 1)
								local after_tool = string.sub(content, end_pos + #M.config.tool_end_marker)
								content = (before_tool .. after_tool):match("^%s*(.-)%s*$") -- trim whitespace
							end
						end

						if content ~= "" then
							return { status = "success", output = content }
						end
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
