local M = {}

local function trim(raw_text)
	local text = tostring(raw_text or "")
	return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function valid_component(value)
	return type(value) == "string" and value ~= "" and value:match("^[A-Za-z0-9_-]+$") ~= nil
end

local function significant_digits(value)
	local significant = value:gsub("^0+", "")
	if significant == "" then
		return nil
	end
	return significant
end

local function unsigned_integer_fits(value, max_value)
	local significant = significant_digits(value)
	if not significant then
		return true
	end
	if #significant ~= #max_value then
		return #significant < #max_value
	end
	return significant <= max_value
end

local function positive_integer_fits(value, max_value)
	return significant_digits(value) ~= nil and unsigned_integer_fits(value, max_value)
end

local function terminal_marker_kind(token)
	local schedule = token:match("^s:(%d+)$")
	if schedule and unsigned_integer_fits(schedule, "18446744073709551615") then
		return "schedule"
	end

	local priority = token:match("^p:(%d+)$")
	if priority and unsigned_integer_fits(priority, "18446744073709551615") then
		return "priority"
	end

	local clip = token:match("^%%(.*)$")
	if not clip then
		return nil
	end
	if clip == "" then
		return "clip"
	end
	if clip:match("^%d+$") then
		if positive_integer_fits(clip, "18446744073709551615") then
			return "clip"
		end
		return nil
	end
	if valid_component(clip) then
		return "clip"
	end
	return nil
end

local function split_tokens(text)
	local tokens = {}
	for start_index, token in text:gmatch("()(%S+)") do
		tokens[#tokens + 1] = {
			start_index = start_index,
			end_index = start_index + #token - 1,
			value = token,
		}
	end
	return tokens
end

local function remove_token(text, token)
	local before = trim(text:sub(1, token.start_index - 1))
	local after = trim(text:sub(token.end_index + 1))
	if before ~= "" and after ~= "" then
		return before .. " " .. after
	end
	return before .. after
end

local function split_interactive_terminal_token(text)
	local tokens = split_tokens(text)
	if #tokens == 0 then
		return "", ""
	end

	local index = #tokens
	local seen_clip = false
	local seen_schedule = false
	local seen_priority = false
	while index > 0 do
		local kind = terminal_marker_kind(tokens[index].value)
		if not kind then
			break
		end
		if kind == "clip" then
			if seen_clip then
				break
			end
			seen_clip = true
		elseif kind == "schedule" then
			if seen_schedule then
				break
			end
			seen_schedule = true
		elseif kind == "priority" then
			if seen_priority then
				break
			end
			seen_priority = true
		end
		index = index - 1
	end

	local token = tokens[index] or tokens[#tokens]
	return remove_token(text, token), token.value
end

local function pomodoro_candidate(token)
	local marker = token:match("^@!(.*)$")
	if marker then
		return true
	end
	marker = token:match("^@(.*)$")
	if not marker then
		return false
	end

	local colon = marker:find(":", 1, true)
	local hash = marker:find("#", 1, true)
	local caret = marker:find("^", 1, true)
	return colon ~= nil and (hash == nil or colon < hash) and (caret == nil or colon < caret)
end

local function sub_bullet_candidate(token)
	local marker = token:match("^@(.*)$")
	if not marker or token:sub(1, 2) == "@!" then
		return false
	end

	local caret = marker:find("^", 1, true)
	local colon = marker:find(":", 1, true)
	local hash = marker:find("#", 1, true)
	return caret ~= nil and (colon == nil or caret < colon) and (hash == nil or caret < hash)
end

local function invalid(message, text)
	return {
		mode = "invalid",
		text = text,
		error = message,
	}
end

local function parse_pomodoro(body, token)
	local legacy = token:sub(1, 2) == "@!"
	local marker = token:sub(legacy and 3 or 2)
	local colon = marker:find(":", 1, true)
	local route
	local block_id

	if colon then
		route = marker:sub(1, colon - 1)
		block_id = marker:sub(colon + 1)
	else
		if not legacy then
			return invalid("Pomodoro capture markers must use @<route>:<block-id>", body)
		end
		route = marker
	end

	if route == "" then
		route = nil
	elseif not valid_component(route) then
		return invalid("Pomodoro capture route must contain only A-Z, a-z, 0-9, '_' or '-'", body)
	else
		route = route:lower()
	end

	if block_id == "" then
		block_id = nil
	elseif block_id and not valid_component(block_id) then
		return invalid("Pomodoro capture block ID must contain only A-Z, a-z, 0-9, '_' or '-'", body)
	end

	if legacy and colon and route == nil then
		return invalid("Legacy Pomodoro shorthand requires a route before ':'", body)
	end

	return {
		mode = "pomodoro",
		text = body,
		route = route,
		block_id = block_id,
		needs_target = route == nil,
		needs_block_id = block_id == nil,
	}
end

local function parse_sub_bullet(body, token)
	local marker = token:sub(2)
	local caret = marker:find("^", 1, true)
	local route = marker:sub(1, caret - 1)
	local block_id = marker:sub(caret + 1)

	if route == "" then
		route = nil
	elseif not valid_component(route) then
		return invalid("sub-bullet capture route must contain only A-Z, a-z, 0-9, '_' or '-'", body)
	else
		route = route:lower()
	end

	if block_id == "" then
		block_id = nil
	elseif block_id:match("^[A-Za-z0-9-]+$") == nil then
		return invalid("sub-bullet capture block ID must be non-empty and contain only A-Z, a-z, 0-9 or '-'", body)
	end

	return {
		mode = "sub_bullet",
		text = body,
		route = route,
		block_id = block_id,
		needs_target = route == nil,
		needs_task = block_id == nil,
	}
end

function M.is_route(value)
	return valid_component(value)
end

function M.is_block_id(value)
	return valid_component(value)
end

function M.new_state()
	return {}
end

function M.reset(state)
	state.request = nil
	state.route = nil
	state.block_id = nil
	state.task_ref = nil
	state.picked_name = nil
	state.picked_kind = nil
	return state
end

function M.stage(state, request, route, block_id, picked_name, picked_kind, task_ref)
	state.request = request
	state.route = route or request.route
	state.block_id = block_id or request.block_id
	state.task_ref = task_ref or request.task_ref
	state.picked_name = picked_name
	state.picked_kind = picked_kind
	return state
end

function M.set_block_id(state, raw_block_id)
	local block_id = trim(raw_block_id)
	state.block_id = block_id
	if not valid_component(block_id) then
		return nil, "Pomodoro capture block ID must be non-empty and contain only A-Z, a-z, 0-9, '_' or '-'"
	end
	return block_id
end

function M.parse(raw_text)
	local text = trim(raw_text)
	local body, token = split_interactive_terminal_token(text)

	if sub_bullet_candidate(token) then
		return parse_sub_bullet(body, token)
	end

	if pomodoro_candidate(token) then
		return parse_pomodoro(body, token)
	end

	local bullet_prefix = token:match("^@#(%S*)$")
	if bullet_prefix then
		if bullet_prefix == "" then
			return { text = body, mode = "note_section" }
		end
		return {
			text = body,
			mode = "note_bullet",
			prefix = bullet_prefix,
		}
	end

	local route = token:match("^@([A-Za-z0-9_-]+)#$")
	if route then
		return {
			text = body,
			mode = "section",
			route = route:lower(),
		}
	end

	if token == "@" then
		return { text = body, mode = "note" }
	end

	return {
		text = text,
		mode = "none",
	}
end

function M.finalize_sub_bullet(request, route, block_id)
	if type(request) ~= "table" or request.mode ~= "sub_bullet" then
		return nil, "Sub-bullet capture request is missing"
	end

	route = route or request.route
	block_id = block_id or request.block_id
	if not valid_component(route) then
		return nil, "sub-bullet capture route must contain only A-Z, a-z, 0-9, '_' or '-'"
	end
	if type(block_id) ~= "string" or block_id == "" or block_id:match("^[A-Za-z0-9-]+$") == nil then
		return nil, "sub-bullet capture block ID must be non-empty and contain only A-Z, a-z, 0-9 or '-'"
	end

	return "@" .. route:lower() .. "^" .. block_id .. " " .. request.text
end

function M.finalize(request, route, block_id)
	if type(request) ~= "table" or request.mode ~= "pomodoro" then
		return nil, "Pomodoro capture request is missing"
	end

	route = route or request.route
	block_id = block_id or request.block_id
	if not valid_component(route) then
		return nil, "Pomodoro capture route must contain only A-Z, a-z, 0-9, '_' or '-'"
	end
	if not valid_component(block_id) then
		return nil, "Pomodoro capture block ID must be non-empty and contain only A-Z, a-z, 0-9, '_' or '-'"
	end

	return "@" .. route:lower() .. ":" .. block_id .. " " .. request.text
end

return M
