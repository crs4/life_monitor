
SHELL := /bin/bash

all: images

images: lifemonitor

certs:
	if [[ ! -d "certs" ]]; then \
	  mkdir certs && \
	  ./utils/certs/gencerts.sh && \
	  cp utils/certs/data/ca.* certs/ && \
	  cp utils/certs/data/lm/*.pem certs/ && \
	  mv certs/ca.pem certs/lifemonitor.ca.crt && \
	  mv certs/cert.pem certs/lm.crt && \
	  mv certs/key.pem certs/lm.key && \
	  chmod 644 certs/*.{key,crt}; \
	fi

lifemonitor: docker/lifemonitor.Dockerfile certs
	docker build -f docker/lifemonitor.Dockerfile -t crs4/lifemonitor .

docker-compose-dev.yml: docker-compose-template.yml
	sed -e "s^LOCAL_PATH^$${PWD}^" \
	    -e "s^USER_UID^$$(id -u)^" \
	    -e "s^USER_GID^$$(id -g)^" \
	    -e "s^FLASK_ENV=production^FLASK_ENV=development^" \
	    -e "s^ALLOW_EMPTY_PASSWORD=no^ALLOW_EMPTY_PASSWORD=yes^" \
	    -e "s^#DEV ^^" \
	    < docker-compose-template.yml > docker-compose-dev.yml

docker-compose-test.yml: docker-compose-template.yml
	sed -e "s^LOCAL_PATH^$${PWD}^" \
	    -e "s^USER_UID^$$(id -u)^" \
	    -e "s^USER_GID^$$(id -g)^" \
	    -e "s^FLASK_ENV=production^FLASK_ENV=development^" \
	    -e "s^ALLOW_EMPTY_PASSWORD=no^ALLOW_EMPTY_PASSWORD=yes^" \
	    -e "s^#DEV ^^" \
	    -e "s^#TEST ^^" \
	    < docker-compose-template.yml > docker-compose-test.yml

docker-compose.yml: docker-compose-template.yml
	sed -e "s^LOCAL_PATH^$${PWD}^" \
	    -e "s^USER_UID^$$(id -u)^" \
	    -e "s^USER_GID^$$(id -g)^" \
	    < docker-compose-template.yml > docker-compose.yml

test_images:
	docker build -f tests/config/registries/seek/seek.Dockerfile \
	       -t crs4/lifemonitor-tests:seek \
	       tests/config/registries/seek/
	

start_test_env: docker-compose-test.yml test_images images
	docker-compose -f ./docker-compose-test.yml up -d ; 

runtests: start_test_env
	docker-compose -f ./docker-compose-test.yml exec -T lm /bin/bash -c "tests/wait-for-it.sh seek:3000 -- pytest tests"

stop_test_env:
	if [[ -f "./docker-compose-test.yml" ]]; then \
	  docker-compose -f ./docker-compose-test.yml down; \
	fi

startdev: docker-compose-dev.yml images
	docker-compose -f ./docker-compose-dev.yml up -d

stopdev:
	if [[ -f "./docker-compose-dev.yml" ]]; then \
	  docker-compose -f ./docker-compose-dev.yml down; \
	fi

start: images docker-compose.yml images
	docker-compose -f ./docker-compose.yml up -d

stop:
	if [[ -f "./docker-compose.yml" ]]; then \
	  docker-compose -f ./docker-compose.yml down; \
	fi

tests: start_test_env
	docker-compose -f ./docker-compose-test.yml exec -T lm /bin/bash -c "tests/wait-for-it.sh seek:3000 -- pytest tests"; \
	  result=$$?; \
	  docker-compose -f ./docker-compose-test.yml down; \
	  exit $$?

clean: stop stopdev
	rm -rf certs docker-compose.yml docker-compose-dev.yml

startshell:
	docker-compose exec lm /bin/bash -c "DEBUG=False flask shell"

.PHONY: all images certs lifemonitor \
		start stop startdev stopdev startshell \
		start_test_env stop_test_env runtests tests clean
