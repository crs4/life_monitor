# set the default interpreter
SHELL := /bin/bash

# set output colors
bold   := $(shell tput bold)
reset  := $(shell tput sgr0)
red    := $(shell tput setaf 1)
green  := $(shell tput setaf 2)
yellow := $(shell tput setaf 3)
done   := $(shell echo "$(green)DONE$(reset)")

# utility function to prepare multi-valued CLI parameters
# Usage: get_opts <PARAM_NAME> <PARAM_VALUE>
#   - PARAM_NAME:  e.g., label, tag
#   - PARAM_VALUE: bash array of values, e.g., (v1 v2 v3)
define get_opts
	$(shell opts=""; values=($(2)); for (( i=0; i<$${#values[@]}; i++)); do opts="$$opts --$(1) '$${values[$$i]}'"; done; echo "$$opts")
endef

# set docker-compose command
ifeq ($(shell command -v "docker-compose" 2> /dev/null),)
	docker_compose := docker compose
else
	docker_compose := docker-compose
endif

# default Docker build options
build_kit :=
build_cmd := build
cache_from_opt :=
cache_to_opt :=
builder :=
ifeq ($(DOCKER_BUILDKIT),1)
	build_kit = DOCKER_BUILDKIT=1
	ifdef BUILDX_BUILDER
		builder_opt = --builder ${BUILDX_BUILDER}
	endif
	build_cmd = buildx build --output=type=docker ${builder_opt}
	ifdef CACHE_TO
		cache_to_opt = --cache-to=$(CACHE_TO)
	endif
endif

# set flag to skip build
skip_build_opt := 0
ifeq ($(SKIP_BUILD),1)
	skip_build_opt := 1
endif

# set the build number
sw_version_arg :=
ifdef SW_VERSION
	sw_version_arg := --build-arg SW_VERSION=$(SW_VERSION)
else
	sw_version_arg := --build-arg SW_VERSION=$$(python3 -c "import lifemonitor; print(lifemonitor.__version__)";)
endif

# set the build number
build_number_arg :=
ifdef BUILD_NUMBER
	build_number_arg := --build-arg BUILD_NUMBER=$(BUILD_NUMBER)
endif

# set cache param
ifdef CACHE_FROM
	cache_from_opt = --cache-from=$(CACHE_FROM)
endif

# handle extra labels
labels_opt :=
ifdef LABELS
	labels_opt := $(call get_opts,label,$(LABELS))
endif

# handle extra tags
tags_opt :=
ifdef TAGS
	tags_opt := $(call get_opts,tag,$(TAGS))
endif

# handle platform option
platforms_opt :=
ifdef PLATFORMS
	platforms_opt := $(call get_opts,platforms,$(PLATFORMS))
endif

# set shared metrics folder
metrics_folder := /tmp/lifemonitor/metrics


all: images

images: lifemonitor smeeio

compose-files: docker-compose.base.yml \
	docker-compose.prod.yml \
	docker-compose.dev.yml \
	docker-compose.extra.yml \
	docker-compose.test.yml \
	docker-compose.prom.yml \
	settings.conf

certs:
	@# Generate certificates if they do not exist \
	if ! [[ -f "certs/lm.key" && -f "certs/lm.key" && -f "certs/lifemonitor.ca.crt" ]]; then \
	  printf "\n$(bold)Generating certificates...$(reset)\n" ; \
	  mkdir -p certs && \
	  ./utils/certs/gencerts.sh && \
	  cp utils/certs/data/ca.* certs/ && \
	  cp utils/certs/data/lm/*.pem certs/ && \
	  mv certs/ca.pem certs/lifemonitor.ca.crt && \
	  mv certs/cert.pem certs/lm.crt && \
	  mv certs/key.pem certs/lm.key && \
	  chmod 644 certs/*.{key,crt}; \
	  printf "\n$(done)\n"; \
	else \
	  echo "$(yellow)WARNING: Using existing certificates$(reset)" ; \
	fi
	@# Generate JWT keys if they do not exist \
	if ! [[ -f "certs/jwt-key" && -f "certs/jwt-key.pub" ]]; then \
	  printf "\n$(bold)Generating JWT keys...$(reset)\n" ; \
	  openssl genrsa -out certs/jwt-key 4096 ; \
	  openssl rsa -in certs/jwt-key -pubout > certs/jwt-key.pub ; \
	  printf "\n$(done)\n"; \
	else \
	  echo "$(yellow)WARNING: Using existing JWT keys $(reset)" ; \
	fi

metrics_folder:
	@if [[ -d $(metrics_folder) ]]; then \
		rm -Rf $(metrics_folder)/* ; \
		printf "\n$(yellow)WARNING: $(bold) Existing metrics folder cleaned up !!! $(reset)\n" ; \
	else \
		mkdir -p $(metrics_folder) ; \
		printf "\n$(bold)Shared metrics folder created !!!$(reset)\n" ; \
	fi

lifemonitor: docker/lifemonitor.Dockerfile certs app.py gunicorn.conf.py ## Build LifeMonitor Docker image
	@if [[ $(skip_build_opt) == 1 ]]; then \
		printf "\n$(yellow)WARNING: $(bold)Skip build of LifeMonitor Docker image !!! $(reset)\n" ; \
	else \
		printf "\n$(bold)Building LifeMonitor Docker image...$(reset)\n" ; \
		$(build_kit) docker $(build_cmd) $(cache_from_opt) $(cache_to_opt) \
			${sw_version_arg} ${build_number_arg} ${tags_opt} ${labels_opt} ${platforms_opt} \
			-f docker/lifemonitor.Dockerfile -t crs4/lifemonitor . ;\
		printf "$(done)\n" ; \
	fi

smeeio:
	@printf "\n$(bold)Building smee.io Docker image...$(reset)\n" ; \
	$(build_kit) docker $(build_cmd) $(cache_from_opt) $(cache_to_opt) \
		  ${tags_opt} ${labels_opt} ${platforms_opt} \
		  -f docker/smee.io.Dockerfile -t crs4/smeeio . ;\
	printf "$(done)\n"

webserver:
	@printf "\n$(bold)Building LifeMonitor WebServer image...$(reset)\n" ; \
	$(build_kit) docker $(build_cmd) $(cache_from_opt) $(cache_to_opt) \
		  ${tags_opt} ${labels_opt} ${platforms_opt} \
		  -f ./tests/config/web/Dockerfile \
		  -t crs4/lifemonitor-tests:webserver \
		  ./tests/config/web ;\
	printf "$(done)\n"


ro_crates:
	@printf "\n$(bold)Preparing RO-Crate archives...$(reset)\n" ; \
	docker run --rm --user $$(id -u):$$(id -g) \
		       -v $$(pwd)/:/data \
			   --entrypoint /bin/bash crs4/lifemonitor -c \
			   "cd /data/tests/config/data && ls && python3 make-test-rocrates.py" ; \
	printf "$(done)\n"

aux_images: tests/config/registries/seek/seek.Dockerfile certs
	@printf "\n$(bold)Building auxiliary Docker images...$(reset)\n" ; \
	docker build -f tests/config/registries/seek/seek.Dockerfile \
	       -t crs4/lifemonitor-tests:seek \
	       tests/config/registries/seek/ ; \
	printf "$(done)\n"

start: images compose-files metrics_folder ## Start LifeMonitor in a Production environment
	@printf "\n$(bold)Starting production services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
			 $(docker_compose) $${base} \
	               -f docker-compose.prod.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.prom.yml \
				   config)" > docker-compose.yml \
	&& $(docker_compose) -f docker-compose.yml up -d redis db init lm worker nginx metrics prometheus;\
	printf "$(done)\n"

start-dev: images compose-files metrics_folder ## Start LifeMonitor in a Development environment
	@printf "\n$(bold)Starting development services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	         $(docker_compose) $${base} \
	               -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   config)" > docker-compose.yml \
	&& $(docker_compose) -f docker-compose.yml up -d redis db dev_proxy github_event_proxy metrics init lm worker ;\
	printf "$(done)\n"

start-testing: compose-files aux_images ro_crates images metrics_folder ## Start LifeMonitor in a Testing environment
	@printf "\n$(bold)Starting testing services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	         $(docker_compose) $${base} \
                   -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   -f docker-compose.test.yml \
				   config)" > docker-compose.yml \
	&& $(docker_compose) -f docker-compose.yml up -d db lmtests seek jenkins webserver worker ;\
	$(docker_compose) -f ./docker-compose.yml \
		exec -T lmtests /bin/bash -c "tests/wait-for-it.sh seek:3000 -t 600"; \
	printf "$(done)\n"

start-nginx: certs docker-compose.prod.yml ## Start a nginx front-end proxy for the LifeMonitor back-end
	@printf "\n$(bold)Starting nginx proxy...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
			 $(docker_compose) $${base} \
					-f docker-compose.prod.yml \
				    -f docker-compose.base.yml config)" > docker-compose.yml \
		  && $(docker_compose) up -d nginx ; \
	printf "$(done)\n"

start-aux-services: aux_images ro_crates docker-compose.extra.yml ## Start auxiliary services (i.e., Jenkins, Seek) useful for development and testing
	@printf "\n$(bold)Starting auxiliary services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	      $(docker_compose) $${base} -f docker-compose.extra.yml config)" > docker-compose.yml \
	      && $(docker_compose) up -d seek jenkins ; \
	printf "$(done)\n"

# start-jupyter: aux_images docker-compose.extra.yml ## Start jupyter service
# 	@printf "\n$(bold)Starting jupyter service...$(reset)\n" ; \
# 	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
# 	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
# 	      $(docker_compose) $${base} -f docker-compose.jupyter.yml config)" > docker-compose.yml \
# 	      && $(docker_compose) up -d jupyter ; \
# 	printf "$(done)\n"

run-tests: start-testing ## Run all tests in the Testing Environment
	@printf "\n$(bold)Running tests...$(reset)\n" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	$(docker_compose) exec -T lmtests /bin/bash -c "pytest --color=yes tests"


tests: start-testing ## CI utility to setup, run tests and teardown a testing environment
	@printf "\n$(bold)Running tests...$(reset)\n" ; \
	$(docker_compose) -f ./docker-compose.yml \
		exec -T lmtests /bin/bash -c "pytest --color=yes tests"; \
	  result=$$?; \
	  	printf "\n$(bold)Teardown services...$(reset)\n" ; \
	  	USER_UID=$$(id -u) USER_GID=$$(id -g) \
		$(docker_compose) -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   -f docker-compose.test.yml \
				   down ; \
		printf "$(done)\n" ; \
	  exit $$?

stop-aux-services: docker-compose.extra.yml ## Stop all auxiliary services (i.e., Jenkins, Seek)
	@echo "$(bold)Teardown auxiliary services...$(reset)" ; \
	$(docker_compose) -f docker-compose.extra.yml --log-level ERROR stop ; \
	printf "$(done)\n"

# stop-jupyter: docker-compose.jupyter.yml ## Stop jupyter service
# 	@echo "$(bold)Stopping auxiliary services...$(reset)" ; \
# 	$(docker_compose) -f docker-compose.jupyter.yml --log-level ERROR stop ; \
# 	printf "$(done)\n"

stop-nginx: docker-compose.yml ## Stop the nginx front-end proxy for the LifeMonitor back-end
	@echo "$(bold)Stopping nginx service...$(reset)" ; \
	$(docker_compose) -f docker-compose.yml stop nginx ; \
	printf "$(done)\n"

stop-testing: compose-files ## Stop all the services in the Testing Environment
	@echo "$(bold)Stopping services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	$(docker_compose) -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   -f docker-compose.test.yml \
				   --log-level ERROR stop db lmtests seek jenkins webserver worker ; \
	printf "$(done)\n"

stop-dev: compose-files ## Stop all services in the Develop Environment
	@echo "$(bold)Stopping development services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	$(docker_compose) -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   stop init lm db github_event_proxy dev_proxy redis worker metrics ; \
	printf "$(done)\n"

stop: compose-files ## Stop all the services in the Production Environment
	@echo "$(bold)Stopping production services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	$(docker_compose) -f docker-compose.base.yml \
				   -f docker-compose.prod.yml \
				   -f docker-compose.prom.yml \
				   --log-level ERROR stop init nginx lm db prometheus metrics redis worker; \
	printf "$(done)\n"

stop-all: ## Stop all the services
	@if [[ -f "docker-compose.yml" ]]; then \
		echo "$(bold)Stopping all services...$(reset)" ; \
		USER_UID=$$(id -u) USER_GID=$$(id -g) \
		$(docker_compose) stop ; \
		printf "$(done)\n" ; \
	else \
		printf "\n$(yellow)WARNING: nothing to remove. 'docker-compose.yml' file not found!$(reset)\n\n" ; \
	fi

down: ## Teardown all the services
	@if [[ -f "docker-compose.yml" ]]; then \
	echo "$(bold)Teardown all services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	$(docker_compose) down ; \
	printf "$(done)\n" ; \
	else \
		printf "\n$(yellow)WARNING: nothing to remove. 'docker-compose.yml' file not found!$(reset)\n\n" ; \
	fi

clean: ## Clean up the working environment (i.e., running services, network, volumes, certs and temp files)
	@if [[ -f "docker-compose.yml" ]]; then \
		echo "$(bold)Teardown all services...$(reset)" ; \
		USER_UID=$$(id -u) USER_GID=$$(id -g) \
		$(docker_compose) down -v --remove-orphans ; \
		printf "$(done)\n"; \
		else \
			printf "$(yellow)WARNING: nothing to remove. 'docker-compose.yml' file not found!$(reset)\n" ; \
	fi
	@printf "\n$(bold)Removing certs...$(reset) " ; \
	rm -rf certs
	rm -rf utils/certs/data
	@printf "$(done)\n"
	@printf "\n$(bold)Removing temp files...$(reset) " ; \
	rm -rf docker-compose.yml
	@printf "$(done)\n\n"

.DEFAULT_GOAL := help

help: ## Show help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: all images aux_images certs metrics_folder \
		lifemonitor smeeio ro_crates webserver \
		start start-dev start-testing start-nginx start-aux-services \
		run-tests tests \
		stop-aux-services stop-nginx stop-testing \
		stop-dev stop stop-all down clean
