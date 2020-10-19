# set the default interpreter
SHELL := /bin/bash

# set output colors
bold   := $(shell tput bold)
reset  := $(shell tput sgr0)
red    := $(shell tput setaf 1)
green  := $(shell tput setaf 2)
yellow := $(shell tput setaf 3)
done   := $(shell echo "$(green)DONE$(reset)")

all: images

images: lifemonitor

compose-files: docker-compose.base.yml \
	docker-compose.prod.yml \
	docker-compose.dev.yml \
	docker-compose.extra.yml

certs:
	@if [[ ! -d "certs" ]]; then \
	  printf "$(red)Generating certificates...$(reset)\n\n" ; \
	  mkdir certs && \
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

lifemonitor: docker/lifemonitor.Dockerfile certs
	@printf "\n$(bold)Building LifeMonitor Docker image...$(reset)\n" ; \
	docker build -f docker/lifemonitor.Dockerfile -t crs4/lifemonitor . ;\
	printf "$(done)\n"

aux_images: tests/config/registries/seek/seek.Dockerfile certs
	@printf "\n$(bold)Building auxiliary Docker images...$(reset)\n" ; \
	docker build -f tests/config/registries/seek/seek.Dockerfile \
	       -t crs4/lifemonitor-tests:seek \
	       tests/config/registries/seek/ ; \
	printf "$(done)\n"

start: images compose-files ## Start LifeMonitor in a Production environment
	@printf "\n$(bold)Starting production services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
			 docker-compose $${base} \
	               -f docker-compose.prod.yml \
				   -f docker-compose.base.yml \
				   config)" > docker-compose.yml \
	&& docker-compose -f docker-compose.yml up -d ;\
	printf "$(done)\n"

start-dev: images compose-files ## Start LifeMonitor in a Development environment
	@printf "\n$(bold)Starting development services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	         docker-compose $${base} \
	               -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   config)" > docker-compose.yml \
	&& docker-compose -f docker-compose.yml up -d ;\
	printf "$(done)\n"

start-testing: compose-files aux_images images ## Start LifeMonitor in a Testing environment
	@printf "\n$(bold)Starting testing services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	         docker-compose $${base} \
                   -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   config)" > docker-compose.yml \
	&& docker-compose -f docker-compose.yml up -d ;\
	docker-compose -f ./docker-compose.yml \
		exec -T lm /bin/bash -c "tests/wait-for-it.sh seek:3000"; \
	printf "$(done)\n"

start-nginx: images docker-compose.prod.yml ## Start a nginx front-end proxy for the LifeMonitor back-end
	@printf "\n$(bold)Starting nginx proxy...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
			 docker-compose $${base} \
					-f docker-compose.prod.yml \
				    -f docker-compose.yml config)" > docker-compose.yml \
		  && docker-compose up -d ; \
	printf "$(done)\n"

start-aux-services: aux_images docker-compose.extra.yml ## Start auxiliary services (i.e., Jenkins, Seek) useful development and testing
	@printf "\n$(bold)Starting auxiliary services...$(reset)\n" ; \
	base=$$(if [[ -f "docker-compose.yml" ]]; then echo "-f docker-compose.yml"; fi) ; \
	echo "$$(USER_UID=$$(id -u) USER_GID=$$(id -g) \
	      docker-compose $${base} -f docker-compose.extra.yml config)" > docker-compose.yml \
	      && docker-compose up -d ; \
	printf "$(done)\n"

run-tests: start-testing ## Run all tests in the Testing Environment
	@printf "\n$(bold)Running tests...$(reset)\n" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	docker-compose exec -T lm /bin/bash -c "pytest --color=yes tests"


tests: start-testing ## CI utility to setup, run tests and teardown a testing environment
	@printf "\n$(bold)Running tests...$(reset)\n" ; \
	docker-compose -f ./docker-compose.yml \
		exec -T lm /bin/bash -c "pytest --color=yes tests"; \
	  result=$$?; \
	  	printf "\n$(bold)Teardown services...$(reset)\n" ; \
	  	USER_UID=$$(id -u) USER_GID=$$(id -g) \
		docker-compose -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   down ; \
		printf "$(done)\n" ; \
	  exit $$?

stop-aux-services: docker-compose.extra.yml ## Stop all auxiliary services (i.e., Jenkins, Seek)
	@echo "$(bold)Teardown auxiliary services...$(reset)" ; \
	docker-compose -f docker-compose.extra.yml --log-level ERROR stop ; \
	printf "$(done)\n"

stop-nginx: docker-compose.yml ## Stop the nginx front-end proxy for the LifeMonitor back-end
	@echo "$(bold)Teardown nginx service...$(reset)" ; \
	docker-compose -f docker-compose.yml stop nginx ; \
	printf "$(done)\n"

stop-testing: compose-files ## Teardown all the services in the Testing Environment
	@echo "$(bold)Teardown services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	docker-compose -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   --log-level ERROR down ; \
	printf "$(done)\n"

stop-dev: compose-files ## Teardown all services in the Develop Environment
	@echo "$(bold)Teardown services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	docker-compose -f docker-compose.base.yml \
				   -f docker-compose.dev.yml \
				   --log-level ERROR down ; \
	printf "$(done)\n"

stop: compose-files ## Teardown all the services in the Production Environment
	@echo "$(bold)Teardown services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	docker-compose -f docker-compose.base.yml \
				   -f docker-compose.prod.yml \
				   --log-level ERROR down ; \
	printf "$(done)\n"

stop-all: ## Teardown all the services
	@echo "$(bold)Teardown services...$(reset)" ; \
	USER_UID=$$(id -u) USER_GID=$$(id -g) \
	docker-compose -f docker-compose.extra.yml \
				   -f docker-compose.base.yml \
				   -f docker-compose.prod.yml \
				   -f docker-compose.dev.yml \
				   --log-level ERROR down \
	&& rm -f docker-compose.yml ; \
	printf "$(done)\n"

clean: stop stop-dev stop-testenv
	rm -rf certs docker-compose.yml

.DEFAULT_GOAL := help

help: ## Show help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: all images aux_images certs lifemonitor \
		start start-dev start-testing start-nginx start-aux-services \
		run-tests tests \
		stop-aux-services stop-nginx stop-testing \
		stop-dev stop stop-all clean
