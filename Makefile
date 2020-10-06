
SHELL := /bin/bash

all: images

images: lifemonitor

certs:
	if [[ ! -d "certs" ]]; then \
		mkdir certs && \
		bash -x ./utils/certs/gencerts.sh && \
		cp utils/certs/data/ca.* certs/ && \
		cp utils/certs/data/lm/*.pem certs/ && \
		mv certs/ca.pem certs/lifemonitor.ca.crt && \
		mv certs/cert.pem certs/lm.crt && \
		mv certs/key.pem certs/lm.key && \
		chmod 644 certs/*.{key,crt}; \
	fi

lifemonitor: docker/lifemonitor.Dockerfile
	docker build -f docker/lifemonitor.Dockerfile -t crs4/lifemonitor .

docker-compose-dev.yml: docker-compose-template.yml
	sed -e "s^LOCAL_PATH^$${PWD}^" \
	    -e "s^USER_UID^$$(id -u)^" \
	    -e "s^USER_GID^$$(id -g)^" \
	    -e "s^FLASK_ENV=production^FLASK_ENV=development^" \
	    -e "s^ALLOW_EMPTY_PASSWORD=no^ALLOW_EMPTY_PASSWORD=yes^" \
	    -e "s^#DEV ^^" \
	    < docker-compose-template.yml > docker-compose-dev.yml


docker-compose.yml: docker-compose-template.yml
	sed -e "s^LOCAL_PATH^$${PWD}^" \
	    -e "s^USER_UID^$$(id -u)^" \
	    -e "s^USER_GID^$$(id -g)^" \
	    < docker-compose-template.yml > docker-compose.yml

startdev: docker-compose-dev.yml images certs
	docker-compose -f ./docker-compose-dev.yml up -d

stopdev:
	if [[ -f "./docker-compose-dev.yml" ]]; then \
		docker-compose -f ./docker-compose-dev.yml down; \
	fi

start: images docker-compose.yml images certs
	docker-compose -f ./docker-compose.yml up -d

stop:
	if [[ -f "./docker-compose.yml" ]]; then \
		docker-compose -f ./docker-compose.yml down; \
	fi

clean: stop stopdev
	rm -rf certs docker-compose.yml docker-compose-dev.yml

.PHONY: all images certs lifemonitor start stop startdev stopdev clean
