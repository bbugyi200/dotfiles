local M = {}

local log = require("plugins.google.codecompanion.goose.log")

---@class BackendConfig
---@field host string
---@field port number
---@field debug boolean

local server_base_command = "blaze run //experimental/users/vintharas/devai-http-wrapper"
local server_log_file = vim.fn.stdpath("cache") .. "/devai-http-wrapper.log"
local server_pid_file = vim.fn.stdpath("cache") .. "/devai-http-wrapper.pid"

---@type BackendConfig
M.config = {
	host = "http://localhost:8080",
	port = 8080,
	debug = false,
}

--- Function to write server pid file
---@type fun(pid: number): boolean
local function write_pid_to_file(pid)
	local f = io.open(server_pid_file, "w")
	if f then
		f:write(tostring(pid))
		f:close()
		log.debug(string.format("DevAI server PID %d written to %s", pid, server_pid_file))
		return true
	else
		log.error(string.format("Error: Failed to write PID to %s", server_pid_file))
		return false
	end
end

--- Reads the PID from the server_pid_file.
---@return number|nil The PID as a number, or nil if file not found or unreadable.
local function read_pid_from_file()
	local f = io.open(server_pid_file, "r")
	if f then
		local pid_str = f:read("*a")
		f:close()
		if pid_str then
			pid_str = pid_str:match("^%s*(%d+)%s*$")
			if pid_str then
				return tonumber(pid_str)
			end
		end
	end
	return nil
end

--- Gets pid for devai wrapper
---@return number|nil
local function get_server_pid()
	if vim.fn.executable("pgrep") == 0 then
		log.warning("pgrep command not found, cannot attempt to find server PID via pgrep.")
		return nil
	end

	local server_identifier = "devai-http-wrapper"
	local pgrep_cmd = string.format("pgrep -nf " .. server_identifier)
	log.debug("Attempting to find server PID with: " .. pgrep_cmd)

	local handle = io.popen(pgrep_cmd)
	local pid_str = nil
	if handle then
		pid_str = handle:read("*a")
		handle:close()
		if pid_str then
			pid_str = pid_str:match("^%s*(%d+)%s*$")
		end
	end

	if pid_str and tonumber(pid_str) then
		log.info("Found PID via pgrep: " .. pid_str)
		return tonumber(pid_str)
	else
		log.debug("Could not find a unique running server process via pgrep with identifier: " .. server_identifier)
		return nil
	end
end

--- Checks if a process with the given PID is running on Linux.
---@param pid number The Process ID to check.
---@return boolean True if the process is running and signalable, false otherwise.
local function is_pid_running(pid)
	if not pid or type(pid) ~= "number" then
		return false
	end
	return os.execute(string.format("kill -0 %d > /dev/null 2>&1", pid)) == 0
end

--- Checks if the DevAI server is responsive by sending a curl request.
---@param host string The server host (e.g., "127.0.0.1", "localhost").
---@param port number The server port.
---@param health_path string? (Optional) The specific path to check. Defaults to "/ping".
---@return boolean True if the server responds successfully, false otherwise or if curl is not found.
local function is_server_responsive_curl(host, port, health_path)
	if not host or not port then
		log.error("Host or port not provided for curl check.")
		return false
	end

	if vim.fn.executable("curl") == 0 then
		log.error("`curl` command not found. Cannot perform DevAI health check.")
		return false
	end

	local path_to_check = health_path or "/ping"
	if path_to_check ~= "" and not string.match(path_to_check, "^/") then
		path_to_check = "/" .. path_to_check
	end
	local target_url = string.format("http://%s:%d%s", host, port, path_to_check)

	local connect_timeout_seconds = 2
	local max_time_seconds = 4

	local curl_command = string.format(
		"curl --head --silent --output /dev/null --fail --connect-timeout %d --max-time %d '%s'",
		connect_timeout_seconds,
		max_time_seconds,
		target_url
	)

	log.debug(string.format("Probing DevAI server with curl: %s", curl_command))

	local success = os.execute(curl_command)

	if success == 0 then
		log.info(string.format("DevAI server is responsive at %s.", target_url))
		return true
	else
		log.debug(
			string.format(
				"DevAI server at %s did not respond successfully (curl exit status: %s).",
				target_url,
				tostring(success)
			)
		)
		return false
	end
end

--- Function to start the server in the background
---@type fun(opts: BackendConfig, silent: boolean|nil)
local function start_server(opts, silent)
	log.info(string.format("Starting DevAI server. Output will be logged to: %s", server_log_file))

	local server_start_command = server_base_command .. " -- --port " .. opts.port
	if opts.debug then
		server_start_command = server_start_command .. " --debug"
	end

	local command_to_run = string.format("nohup %s > %s 2>&1 &", server_start_command, server_log_file)

	log.debug(string.format("Executing: %s", command_to_run))

	local success = os.execute(command_to_run)

	if success then
		log.info(string.format("DevAI server start command issued. Check log for details: %s", server_log_file))
		vim.defer_fn(function()
			if is_server_responsive_curl(opts.host, opts.port) then
				log.info("DevAI server appears to be listening on port " .. opts.port .. " after start.")
			else
				log.warning(
					"DevAI server was started, but port " .. opts.port .. " is not yet active. Check server log."
				)
			end
			if not silent then
				vim.notify("Dev AI server started.", vim.log.levels.INFO)
			end
			local pid_found = get_server_pid()
			if pid_found then
				write_pid_to_file(pid_found)
			end
		end, 1500)
	else
		log.error(string.format("Failed to issue server start command. Command: %s", command_to_run))
	end
end

--- Stops DevAI server
---@type fun()
local function stop_server()
	local pid = read_pid_from_file()

	if not pid then
		log.debug("Could not find pid in file.")
		pid = get_server_pid()
		if not pid then
			log.info("DevAI server is not currently active.")
			return
		end
	end

	if not is_pid_running(pid) then
		log.info("DevAI server is not currently active.")
		log.warning(string.format("Removing stale PID file: %s", pid, server_pid_file))
		os.remove(server_pid_file)
		return
	end

	log.info(string.format("Attempting to stop server...", pid))

	log.debug(string.format("Sending SIGKILL to PID %d...", pid))
	os.execute(string.format("kill -9 %d", pid))

	vim.defer_fn(function()
		if is_pid_running(pid) then
			log.error(
				string.format(
					"Error: Failed to terminate server PID %d even with SIGKILL. Manual intervention may be required.",
					pid
				)
			)
		else
			log.info(string.format("DevAI server with PID %d terminated with SIGKILL.", pid))
			vim.notify(string.format("DevAI server stopped.", pid), vim.log.levels.INFO)
		end
	end, 1500)

	if os.remove(server_pid_file) then
		log.debug(string.format("PID file %s removed.", server_pid_file))
	else
		log.warning(
			string.format(
				"Warning: Could not remove PID file %s (it may have been already removed or there was a permission issue).",
				server_pid_file
			)
		)
	end
end

--- Sets up DevAI server configuration.
---@type fun(config: BackendConfig)
function M.setup(opts)
	M.config = vim.tbl_deep_extend("force", M.config, opts or {})
end

--- Starts DevAI server
---@param silent boolean|nil Whether to silence messages
function M.start(silent)
	if not silent then
		vim.notify("Checking if local DevAI server is running...", vim.log.levels.INFO)
	end

	if is_server_responsive_curl(M.config.host, M.config.port) then
		if not silent then
			vim.notify(
				string.format("DevAI server is already listening on %s:%d.", M.config.host, M.config.port),
				vim.log.levels.INFO
			)
		end
	else
		if not silent then
			vim.notify(
				string.format("No server detected on %s:%d. Attempting to start.", M.config.host, M.config.port),
				vim.log.levels.INFO
			)
		end
		start_server(M.config, silent)
	end
end

--- Get server status
---@type fun()
function M.get_status()
	vim.notify("Checking if local DevAI server is running...", vim.log.levels.INFO)

	if is_server_responsive_curl(M.config.host, M.config.port) then
		vim.notify(
			string.format("DevAI server is already listening on %s:%d.", M.config.host, M.config.port),
			vim.log.levels.INFO
		)
	else
		vim.notify(string.format("No server detected on %s:%d.", M.config.host, M.config.port), vim.log.levels.INFO)
	end
end

--- Stops DevAI server
---@type fun()
function M.stop()
	vim.notify("Checking if local DevAI server is running...", vim.log.levels.INFO)

	if is_server_responsive_curl(M.config.host, M.config.port) then
		vim.notify(
			string.format("DevAI server listening on %s:%d. Attempting to stop server.", M.config.host, M.config.port),
			vim.log.levels.INFO
		)
		stop_server()
	else
		vim.notify(string.format("No server detected on %s:%d.", M.config.host, M.config.port), vim.log.levels.INFO)
		start_server(M.config)
	end
end

return M
