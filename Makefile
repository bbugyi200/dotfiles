.DEFAULT_GOAL := help

DOCKER_CMD := USER_ID=$(shell id -u) GROUP_ID=$(shell id -g) docker compose run --rm bbugyi200.dotfiles
MAKE_CMD := make -f targets.mk
USE_DOCKER_FILE := .lcldev/use-docker

# If .lcldev/use-docker exists, then set `USE_DOCKER` to True
ifneq ("$(wildcard $(USE_DOCKER_FILE))","")
	USE_DOCKER := True
endif

ifdef USE_DOCKER
	MAKE_CMD := $(DOCKER_CMD) $(MAKE_CMD)
endif

.DEFAULT:
	$(MAKE_CMD) $@

.PHONY: clean
clean: docker-clean ## Remove ALL build artifacts.

.PHONY: docker-clean
docker-clean: ## Remove docker build artifacts.
	docker image rm --force chezmoi-bbugyi200.dotfiles:latest

.PHONY: docker-off
docker-off: ## Remove docker switch file so that subsequent `make` commands run locally.
	$(RM) $(USE_DOCKER_FILE)

.PHONY: docker-on
docker-on: ## Create docker switch file so that subsequent `make` commands run inside docker container.
	test -d .lcldev || mkdir .lcldev
	touch $(USE_DOCKER_FILE)

.PHONY: help
help: ## Print this message. [default]
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' targets.mk $(MAKEFILE_LIST) | sort
