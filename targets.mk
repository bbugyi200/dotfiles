.DELETE_ON_ERROR:
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
MAKEFLAGS += --warn-undefined-variables
SHELL := /bin/bash

.PHONY: test
test:  ## Run dotfile tests.
	busted ./home/dot_config/nvim
