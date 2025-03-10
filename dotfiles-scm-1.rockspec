---@diagnostic disable: lowercase-global

rockspec_format = "3.0"
package = "dotfiles"
version = "scm-1"

test_dependencies = {
	"lua >= 5.1",
	"nlua",
}

source = {
	url = "git://github.com/bbugyi200/" .. package,
}

build = {
	type = "builtin",
}
