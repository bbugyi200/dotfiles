local M = {}

--- Extract host and port from a URL
---@param url string The URL to parse
---@return string, number The host and port
function M.extract_host_port(url)
	-- Remove protocol if present
	local clean_url = url:gsub("^https?://", "")

	-- Split on the first colon to separate host and port
	local host, port_and_path = clean_url:match("^([^:]+):?(.*)$")

	if not host then
		error("Invalid URL format: " .. url)
	end

	---@type number?
	local port
	if port_and_path and port_and_path ~= "" then
		-- Extract port number (before any path)
		local port_str = port_and_path:match("^(%d+)")
		if port_str then
			port = tonumber(port_str)
		end
	end

	return host, port or 80
end

return M

