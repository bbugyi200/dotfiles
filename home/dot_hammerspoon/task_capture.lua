local M = {}

local function trim(raw_text)
	local text = tostring(raw_text or "")
	return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function valid_component(value)
	return type(value) == "string" and value ~= "" and value:match("^[A-Za-z0-9_-]+$") ~= nil
end

local function split_terminal_token(text)
	local body, token = text:match("^(.-)%s+(%S+)$")
	if body then
		return trim(body), token
	end
	return "", text
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
	return colon ~= nil and (hash == nil or colon < hash)
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
	state.picked_name = nil
	state.picked_kind = nil
	return state
end

function M.stage(state, request, route, block_id, picked_name, picked_kind)
	state.request = request
	state.route = route or request.route
	state.block_id = block_id or request.block_id
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
	local body, token = split_terminal_token(text)

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
